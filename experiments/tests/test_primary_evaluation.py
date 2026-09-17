import json
import tempfile
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas

from experiments.primary_confidence import (
    CLASSIFICATION_INSTRUCTIONS,
    DIAGNOSTIC_IDS,
    FEATURE_IDS,
    PROMPT_ID,
    SCHEMA_ID,
    TEXT_FORMAT,
)
from experiments.primary_evaluation import (
    EVALUATION_CONFIG_ID,
    EVALUATION_INSTRUCTIONS,
    EVALUATION_PROMPT_ID,
    EVALUATION_SCHEMA_ID,
    EVALUATION_TEXT_FORMAT,
    SPEND_GUARDRAILS_USD,
    V1_EVALUATION_CONFIG_ID,
    build_evaluation_request_parameters,
    build_sanitized_report,
    extract_manifest_records,
    extract_pdf_pages,
    load_manifest,
    run_primary_evaluation,
    select_records_by_id,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "evaluation" / "manifest.json"
V2_MANIFEST_PATH = REPOSITORY_ROOT / "evaluation" / "manifest-v2.json"


class PrimaryEvaluationTests(unittest.TestCase):
    def make_payload(self, candidate_class: str) -> dict:
        return {
            "candidate_class": candidate_class,
            "features": {
                feature_id: {"status": "absent", "evidence": None}
                for feature_id in FEATURE_IDS
            },
            "diagnostics": {
                diagnostic_id: {"status": "absent", "evidence": None}
                for diagnostic_id in DIAGNOSTIC_IDS
            },
        }

    def test_v1_manifest_remains_a_separate_balanced_historical_set(self):
        manifest = load_manifest(MANIFEST_PATH)
        documents = manifest["documents"]

        tuning = [item for item in documents if item["split"] == "tuning"]
        heldout = [item for item in documents if item["split"] == "heldout"]
        self.assertEqual(len(tuning), 12)
        self.assertEqual(len(heldout), 10)
        self.assertTrue(
            all(item["split"] == "tuning" for item in documents if item["used_in_g1"])
        )
        self.assertFalse(
            {item["template_group"] for item in tuning}
            & {item["template_group"] for item in heldout}
        )

    def test_v2_manifest_reuses_only_failed_examples_for_targeted_tuning(self):
        manifest = load_manifest(V2_MANIFEST_PATH)
        tuning = [item for item in manifest["documents"] if item["split"] == "tuning"]
        heldout = [item for item in manifest["documents"] if item["split"] == "heldout"]

        self.assertEqual(manifest["parent_manifest"], "manifest.json")
        self.assertEqual(
            {item["id"] for item in tuning},
            {"v2-tuning-packing-list", "v2-tuning-purchase-order"},
        )
        self.assertEqual({item["expected_label"] for item in tuning}, {"OTHER"})
        self.assertEqual(len(heldout), 10)
        self.assertEqual(
            {item["expected_label"] for item in heldout},
            {"BOL", "POD", "INVOICE", "OTHER", None},
        )
        self.assertTrue(
            all(Path(item["path"]).name.startswith("v2-heldout-") for item in heldout)
        )

        v1_groups = {
            item["template_group"]
            for item in load_manifest(MANIFEST_PATH)["documents"]
            if item["split"] == "heldout"
        }
        self.assertFalse(v1_groups & {item["template_group"] for item in heldout})

    def test_all_redistributable_fixtures_exist_and_extract_as_one_page_text_pdfs(self):
        for manifest_path, expected_count in (
            (MANIFEST_PATH, 18),
            (V2_MANIFEST_PATH, 12),
        ):
            manifest = load_manifest(manifest_path)
            redistributable = [
                item
                for item in manifest["documents"]
                if item["redistribution"] == "allowed"
            ]
            self.assertEqual(len(redistributable), expected_count)
            for item in redistributable:
                path = (manifest_path.parent / item["path"]).resolve()
                self.assertTrue(path.is_file(), item["id"])

            heldout_records = extract_manifest_records(manifest_path, "heldout")
            self.assertEqual(len(heldout_records), 10)
            self.assertTrue(all(len(record["pages"]) == 1 for record in heldout_records))
            self.assertTrue(all(record["pages"][0] for record in heldout_records))

    def test_v1_tuning_records_include_g1_controls_and_synthetic_challenges(self):
        records = extract_manifest_records(MANIFEST_PATH, "tuning")

        self.assertEqual(len(records), 12)
        self.assertEqual(
            {record["expected_class"] for record in records},
            {"INVOICE", "BOL", "POD", "OTHER", None},
        )
        self.assertIn(
            "UNCERTAIN_NO_FALLBACK",
            {record["expected_outcome"] for record in records},
        )
        self.assertIn("ESCALATE", {record["expected_outcome"] for record in records})

    def test_pdf_extraction_redacts_payment_identifiers_before_model_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sensitive.pdf"
            pdf = canvas.Canvas(str(path), invariant=1, pageCompression=0)
            pdf.drawString(50, 750, "Account Number: 123456789")
            pdf.drawString(50, 730, "Routing Number: 987654321")
            pdf.drawString(50, 710, "SWIFT Code: FAKEUS00")
            pdf.save()

            pages = extract_pdf_pages(path, "sensitive-fixture")

        extracted = "\n".join(pages)
        self.assertEqual(extracted.count("[REDACTED]"), 3)
        self.assertNotIn("123456789", extracted)
        self.assertNotIn("987654321", extracted)
        self.assertNotIn("FAKEUS00", extracted)

    def test_v2_prompt_and_schema_broaden_only_non_target_identity(self):
        self.assertEqual(PROMPT_ID, "primary-classification-evidence-v1")
        self.assertEqual(SCHEMA_ID, "primary-classification-evidence-v1")
        self.assertEqual(TEXT_FORMAT["name"], "primary_classification_evidence")
        self.assertIn("such as commercial/customs invoice", CLASSIFICATION_INSTRUCTIONS)
        self.assertNotIn("packing list", CLASSIFICATION_INSTRUCTIONS)

        self.assertEqual(EVALUATION_PROMPT_ID, "primary-classification-evidence-v2")
        self.assertEqual(EVALUATION_SCHEMA_ID, "primary-classification-evidence-v2")
        self.assertEqual(
            EVALUATION_TEXT_FORMAT["name"],
            "primary_classification_evidence_v2",
        )
        self.assertIn("packing list", EVALUATION_INSTRUCTIONS)
        self.assertIn("purchase order", EVALUATION_INSTRUCTIONS)
        description = EVALUATION_TEXT_FORMAT["schema"]["properties"]["features"][
            "properties"
        ]["non_target_identity"]["description"]
        self.assertIn("packing list", description)

        request = build_evaluation_request_parameters("WAREHOUSE PICK LIST")
        self.assertEqual(request["instructions"], EVALUATION_INSTRUCTIONS)
        self.assertEqual(request["text"]["format"], EVALUATION_TEXT_FORMAT)
        self.assertFalse(request["store"])

    def test_targeted_selection_preserves_requested_order_and_rejects_unknown_ids(self):
        records = extract_manifest_records(V2_MANIFEST_PATH, "tuning")
        selected = select_records_by_id(
            records,
            ["v2-tuning-purchase-order", "v2-tuning-packing-list"],
        )
        self.assertEqual(
            [record["document_id"] for record in selected],
            ["v2-tuning-purchase-order", "v2-tuning-packing-list"],
        )
        with self.assertRaises(ValueError):
            select_records_by_id(records, ["missing"])

    def test_representative_runner_uses_v2_contract_and_adds_routing_counts(self):
        records = extract_manifest_records(V2_MANIFEST_PATH, "heldout")[:2]
        requests = []

        def request(parameters):
            requests.append(parameters)
            return {
                "response_id": "response-evaluation",
                "status": "completed",
                "output_text": json.dumps(self.make_payload("BOL")),
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "reasoning_tokens": 10,
                },
                "latency_seconds": 0.1,
            }

        summary = run_primary_evaluation(records, request)

        self.assertEqual(summary["config_id"], EVALUATION_CONFIG_ID)
        self.assertEqual(summary["prompt_id"], EVALUATION_PROMPT_ID)
        self.assertEqual(summary["schema_id"], EVALUATION_SCHEMA_ID)
        self.assertEqual(summary["expected_count"], 2)
        self.assertEqual(summary["call_count"], 2)
        self.assertEqual(summary["outcome_counts"]["unnecessary_escalation"], 2)
        self.assertEqual(SPEND_GUARDRAILS_USD["tuning"], 0.02)
        self.assertEqual(SPEND_GUARDRAILS_USD["heldout"], 0.05)
        self.assertTrue(
            all(item["instructions"] == EVALUATION_INSTRUCTIONS for item in requests)
        )

        report = build_sanitized_report(summary)
        self.assertEqual(report["routing_rules_id"], "critical-combinations-primary-v1")
        self.assertEqual(report["score_method"], "critical-feature-coverage-v1")
        self.assertEqual(report["acceptance_threshold"], 1.0)
        self.assertNotIn("model_output", report["results"][0])
        self.assertNotIn("attempts", report["results"][0])

    def test_v1_manifest_remains_runnable_with_the_frozen_v1_contract(self):
        records = extract_manifest_records(MANIFEST_PATH, "heldout")[:1]
        requests = []

        def request(parameters):
            requests.append(parameters)
            return {
                "response_id": "response-v1-replay",
                "status": "completed",
                "output_text": json.dumps(self.make_payload("BOL")),
                "usage": {},
                "latency_seconds": 0.1,
            }

        summary = run_primary_evaluation(records, request)

        self.assertEqual(summary["config_id"], V1_EVALUATION_CONFIG_ID)
        self.assertEqual(summary["prompt_id"], PROMPT_ID)
        self.assertEqual(summary["schema_id"], SCHEMA_ID)
        self.assertEqual(requests[0]["instructions"], CLASSIFICATION_INSTRUCTIONS)
        self.assertEqual(requests[0]["text"]["format"], TEXT_FORMAT)

    def test_prior_spend_is_counted_against_the_phase_guardrail(self):
        records = extract_manifest_records(V2_MANIFEST_PATH, "tuning")[:1]
        calls = 0

        def request(parameters):
            nonlocal calls
            calls += 1
            return {
                "response_id": "should-not-run",
                "status": "completed",
                "output_text": json.dumps(self.make_payload("OTHER")),
                "usage": {},
                "latency_seconds": 0.1,
            }

        summary = run_primary_evaluation(records, request, prior_spend_usd=0.015)

        self.assertEqual(calls, 0)
        self.assertTrue(summary["halted"])
        self.assertEqual(
            summary["results"][0]["error_category"],
            "spend_guardrail_reached",
        )


if __name__ == "__main__":
    unittest.main()
