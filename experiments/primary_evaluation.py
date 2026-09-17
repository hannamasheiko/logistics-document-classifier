import argparse
import json
import os
from copy import deepcopy
from pathlib import Path

from pypdf import PdfReader

from experiments.deterministic_routing import (
    PRIMARY_ACCEPTANCE_THRESHOLD,
    PRIMARY_ROUTING_RULES_ID,
    PRIMARY_SCORE_METHOD_ID,
    evaluate_primary_routing,
)
from experiments.extract_control_text import redact_sensitive_values
from experiments.primary_confidence import (
    CLASSIFICATION_INSTRUCTIONS,
    MODEL,
    PROMPT_ID,
    SCHEMA_ID,
    TEXT_FORMAT,
    build_request_parameters,
    create_openai_client,
    ensure_execution_allowed,
    request_openai,
    run_experiment,
    write_summary,
)


EVALUATION_CONFIG_ID = "primary-text-evaluation-v2"
EVALUATION_PROMPT_ID = "primary-classification-evidence-v2"
EVALUATION_SCHEMA_ID = "primary-classification-evidence-v2"
SPEND_GUARDRAILS_USD = {"tuning": 0.02, "heldout": 0.05}
V1_EVALUATION_CONFIG_ID = "primary-text-evaluation-v1"
V1_SPEND_GUARDRAILS_USD = {"tuning": 0.10, "heldout": 0.06}
VALID_SPLITS = {"tuning", "heldout"}
VALID_LABELS = {"INVOICE", "BOL", "POD", "OTHER"}
VALID_OUTCOMES = {"ACCEPT", "ESCALATE", "UNCERTAIN_NO_FALLBACK"}

V1_NON_TARGET_INSTRUCTION = (
    "- `non_target_identity`: the document itself identifies a non-target type such "
    "as commercial/customs invoice."
)
V2_NON_TARGET_INSTRUCTION = (
    "- `non_target_identity`: the document explicitly identifies any document type "
    "outside BOL, POD, and transport/logistics-service invoice, including but not "
    "limited to commercial/customs invoice, packing list, purchase order, or customs "
    "declaration. An explicit non-target title establishes identity, but does not by "
    "itself establish the document's primary purpose."
)
EVALUATION_INSTRUCTIONS = CLASSIFICATION_INSTRUCTIONS.replace(
    V1_NON_TARGET_INSTRUCTION,
    V2_NON_TARGET_INSTRUCTION,
)
if EVALUATION_INSTRUCTIONS == CLASSIFICATION_INSTRUCTIONS:
    raise RuntimeError("The V2 prompt patch did not match the frozen V1 prompt.")

EVALUATION_TEXT_FORMAT = deepcopy(TEXT_FORMAT)
EVALUATION_TEXT_FORMAT["name"] = "primary_classification_evidence_v2"
EVALUATION_TEXT_FORMAT["schema"]["properties"]["features"]["properties"][
    "non_target_identity"
]["description"] = (
    "The document explicitly identifies any non-target document type outside BOL, "
    "POD, and transport/logistics-service invoice; examples include commercial or "
    "customs invoice, packing list, purchase order, and customs declaration."
)


def build_evaluation_request_parameters(document_text: str) -> dict:
    parameters = build_request_parameters(document_text)
    parameters["instructions"] = EVALUATION_INSTRUCTIONS
    parameters["text"] = {"format": EVALUATION_TEXT_FORMAT}
    return parameters


def load_manifest(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported evaluation manifest schema version.")
    if set(manifest.get("taxonomy", [])) != VALID_LABELS:
        raise ValueError("Manifest taxonomy does not match the agreed classes.")

    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("Manifest must contain evaluation documents.")

    ids = [document.get("id") for document in documents]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError("Manifest document IDs must be present and unique.")

    groups_by_split = {split: set() for split in VALID_SPLITS}
    for document in documents:
        split = document.get("split")
        if split not in VALID_SPLITS:
            raise ValueError("Every document must use a known split.")
        group = document.get("template_group")
        if not group:
            raise ValueError("Every document must have a template group.")
        groups_by_split[split].add(group)

        label = document.get("expected_label")
        outcome = document.get("expected_outcome")
        if label not in VALID_LABELS | {None}:
            raise ValueError("Expected labels must use the agreed taxonomy or null.")
        if outcome not in VALID_OUTCOMES:
            raise ValueError("Every document must have a known expected outcome.")
        if outcome == "ACCEPT" and label is None:
            raise ValueError("Accepted documents require an expected label.")
        if document.get("used_in_g1") and split != "tuning":
            raise ValueError("G1 controls cannot be held-out documents.")
        if document.get("redistribution") not in {"allowed", "not-established"}:
            raise ValueError("Every document needs a redistribution status.")

    if groups_by_split["tuning"] & groups_by_split["heldout"]:
        raise ValueError("Template groups cannot cross tuning and held-out splits.")

    required_coverage_splits = {"heldout"}
    if not manifest.get("parent_manifest"):
        required_coverage_splits.add("tuning")
    for split in required_coverage_splits:
        split_labels = {
            document["expected_label"]
            for document in documents
            if document["split"] == split and document["expected_label"] is not None
        }
        if split_labels != VALID_LABELS:
            raise ValueError(f"The {split} split must cover all agreed classes.")


def resolve_document_path(manifest_path: Path, document: dict) -> Path:
    return (manifest_path.parent / document["path"]).resolve()


def extract_pdf_pages(pdf_path: Path, document_id: str) -> list[str]:
    reader = PdfReader(pdf_path, strict=False)
    if reader.is_encrypted:
        raise ValueError(f"Evaluation PDF is encrypted: {document_id}")
    pages = [
        redact_sensitive_values((page.extract_text() or "").strip())
        for page in reader.pages
    ]
    if not 1 <= len(pages) <= 10:
        raise ValueError(f"Evaluation PDF has an invalid page count: {document_id}")
    return pages


def extract_manifest_records(manifest_path: Path, split: str) -> list[dict]:
    if split not in VALID_SPLITS:
        raise ValueError("Unknown evaluation split.")
    manifest = load_manifest(manifest_path)
    evaluation_version = manifest.get("evaluation_version", 1)
    records = []
    for document in manifest["documents"]:
        if document["split"] != split:
            continue
        pdf_path = resolve_document_path(manifest_path, document)
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Evaluation PDF is unavailable: {document['id']}")
        pages = extract_pdf_pages(pdf_path, document["id"])
        records.append(
            {
                "document_id": document["id"],
                "source_file": pdf_path.name,
                "expected_class": document["expected_label"],
                "expected_outcome": document["expected_outcome"],
                "evaluation_version": evaluation_version,
                "split": split,
                "template_group": document["template_group"],
                "redistribution": document["redistribution"],
                "pages": pages,
            }
        )
    return records


def select_records_by_id(records: list[dict], document_ids: list[str]) -> list[dict]:
    if len(document_ids) != len(set(document_ids)):
        raise ValueError("Each requested document ID must be unique.")
    records_by_id = {record["document_id"]: record for record in records}
    selected = [
        records_by_id[document_id]
        for document_id in document_ids
        if document_id in records_by_id
    ]
    if len(selected) != len(document_ids):
        raise ValueError("Each requested document ID must exist in the selected split.")
    return selected


def add_routing_results(summary: dict) -> dict:
    counts = {
        "accepted_correct": 0,
        "accepted_incorrect": 0,
        "expected_escalation": 0,
        "unnecessary_escalation": 0,
        "semantic_uncertainty_correct": 0,
        "semantic_uncertainty_incorrect": 0,
        "technical_or_invalid": 0,
    }
    for result in summary["results"]:
        if result["status"] != "completed":
            counts["technical_or_invalid"] += 1
            continue
        routing = evaluate_primary_routing(result["model_output"])
        result["routing"] = routing
        action = routing["action"]
        expected_outcome = result["expected_outcome"]
        expected_class = result["expected_class"]
        if action == "ACCEPT":
            if expected_outcome == "ACCEPT" and routing["candidate_class"] == expected_class:
                counts["accepted_correct"] += 1
            else:
                counts["accepted_incorrect"] += 1
        elif action == "UNCERTAIN_NO_FALLBACK":
            key = (
                "semantic_uncertainty_correct"
                if expected_outcome == "UNCERTAIN_NO_FALLBACK"
                else "semantic_uncertainty_incorrect"
            )
            counts[key] += 1
        elif expected_outcome == "ESCALATE":
            counts["expected_escalation"] += 1
        else:
            counts["unnecessary_escalation"] += 1
    summary["outcome_counts"] = counts
    return summary


def run_primary_evaluation(
    records: list[dict],
    request,
    prior_spend_usd: float = 0.0,
    spend_guardrail_usd: float | None = None,
) -> dict:
    splits = {record.get("split") for record in records}
    if len(splits) != 1 or None in splits:
        raise ValueError("One evaluation run must contain exactly one split.")
    split = splits.pop()
    versions = {record.get("evaluation_version", 1) for record in records}
    if len(versions) != 1:
        raise ValueError("One evaluation run must contain exactly one contract version.")
    evaluation_version = versions.pop()
    if evaluation_version == 1:
        approved_budgets = V1_SPEND_GUARDRAILS_USD
        config_id = V1_EVALUATION_CONFIG_ID
        prompt_id = PROMPT_ID
        schema_id = SCHEMA_ID
        request_builder = build_request_parameters
    elif evaluation_version == 2:
        approved_budgets = SPEND_GUARDRAILS_USD
        config_id = EVALUATION_CONFIG_ID
        prompt_id = EVALUATION_PROMPT_ID
        schema_id = EVALUATION_SCHEMA_ID
        request_builder = build_evaluation_request_parameters
    else:
        raise ValueError("Unknown evaluation contract version.")
    if split not in approved_budgets:
        raise ValueError("Unknown evaluation split.")
    approved_guardrail = approved_budgets[split]
    if spend_guardrail_usd is None:
        spend_guardrail_usd = approved_guardrail
    if not 0 < spend_guardrail_usd <= approved_guardrail:
        raise ValueError("Spend guardrail exceeds the approved split budget.")
    summary = run_experiment(
        records,
        request,
        require_full_set=False,
        representative_set=True,
        max_calls=len(records) * 2,
        spend_guardrail_usd=spend_guardrail_usd,
        config_id=config_id,
        prompt_id=prompt_id,
        schema_id=schema_id,
        model=MODEL,
        request_builder=request_builder,
        prior_spend_usd=prior_spend_usd,
    )
    return add_routing_results(summary)


def build_sanitized_report(summary: dict) -> dict:
    report = {
        key: summary.get(key)
        for key in (
            "provider",
            "endpoint",
            "config_id",
            "prompt_id",
            "schema_id",
            "model",
            "expected_count",
            "call_count",
            "estimated_spend_usd",
            "prior_spend_usd",
            "cumulative_estimated_spend_usd",
            "halted",
        )
    }
    report["outcome_counts"] = summary.get(
        "outcome_counts",
        summary.get("provisional_outcome_counts"),
    )
    report.update(
        {
            "routing_rules_id": PRIMARY_ROUTING_RULES_ID,
            "score_method": PRIMARY_SCORE_METHOD_ID,
            "acceptance_threshold": PRIMARY_ACCEPTANCE_THRESHOLD,
            "results": [],
        }
    )
    for result in summary["results"]:
        item = {
            key: result.get(key)
            for key in (
                "document_id",
                "split",
                "template_group",
                "redistribution",
                "expected_class",
                "expected_outcome",
                "status",
                "error_category",
            )
            if result.get(key) is not None
        }
        if result.get("status") == "completed":
            routing = evaluate_primary_routing(result["model_output"])
            item.update(
                {
                    "candidate_class": result["model_output"]["candidate_class"],
                    "routing_action": routing["action"],
                    "routing_reason": routing["reason"],
                    "routing_score": routing["routing_score"],
                    "complete_classes": routing["complete_classes"],
                }
            )
        report["results"].append(item)
    return report


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one bounded split of the primary classification evaluation."
    )
    parser.add_argument("--run-live", action="store_true")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--split", required=True, choices=sorted(VALID_SPLITS))
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--prior-spend-usd", type=float, default=0.0)
    parser.add_argument("--only-id", action="append")
    parser.add_argument("--spend-guardrail-usd", type=float)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    ensure_execution_allowed(arguments.run_live, os.environ)
    records = extract_manifest_records(arguments.manifest, arguments.split)
    if arguments.only_id:
        records = select_records_by_id(records, arguments.only_id)
    client = create_openai_client()
    summary = run_primary_evaluation(
        records,
        lambda parameters: request_openai(client, parameters),
        prior_spend_usd=arguments.prior_spend_usd,
        spend_guardrail_usd=arguments.spend_guardrail_usd,
    )
    write_summary(summary, arguments.output_json)
    completed = sum(result["status"] == "completed" for result in summary["results"])
    print(
        f"{arguments.split} evaluation: {completed}/{summary['expected_count']} completed, "
        f"{summary['call_count']} calls, ${summary['estimated_spend_usd']:.6f} run spend, "
        f"${summary['cumulative_estimated_spend_usd']:.6f} cumulative."
    )
    print(f"Local raw result: {arguments.output_json}")
    return 1 if summary["halted"] or completed != summary["expected_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
