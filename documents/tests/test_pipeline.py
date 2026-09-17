import json
import shutil
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from reportlab.pdfgen import canvas

from documents.ai.classification import (
    DIAGNOSTIC_IDS,
    FEATURE_IDS,
    NonRetryableRequestFailure,
    RetryableRequestFailure,
)
from documents.forms import DocumentUploadForm
from documents.models import ProcessingAttempt
from documents.services.pdf import extract_text
from documents.services.processing import run_classification


def make_text_pdf(lines: list[str]) -> bytes:
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=(612, 792))
    y = 750
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.showPage()
    page.save()
    return buffer.getvalue()


def make_image_only_pdf() -> bytes:
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=(200, 200))
    page.rect(10, 10, 50, 50, fill=1)
    page.showPage()
    page.save()
    return buffer.getvalue()


def make_observations(candidate_class, evidence_by_feature=None, evidence_by_diagnostic=None):
    evidence_by_feature = evidence_by_feature or {}
    evidence_by_diagnostic = evidence_by_diagnostic or {}
    return {
        "candidate_class": candidate_class,
        "features": {
            feature_id: (
                {"status": "present", "evidence": evidence_by_feature[feature_id]}
                if feature_id in evidence_by_feature
                else {"status": "absent", "evidence": None}
            )
            for feature_id in FEATURE_IDS
        },
        "diagnostics": {
            diagnostic_id: (
                {"status": "present", "evidence": evidence_by_diagnostic[diagnostic_id]}
                if diagnostic_id in evidence_by_diagnostic
                else {"status": "absent", "evidence": None}
            )
            for diagnostic_id in DIAGNOSTIC_IDS
        },
    }


def completed_response(observations: dict) -> dict:
    return {
        "response_id": "response-1",
        "status": "completed",
        "output_text": json.dumps(observations),
        "usage": {"input_tokens": 100, "output_tokens": 50, "reasoning_tokens": 10},
        "latency_seconds": 0.2,
    }


def make_dual_request(primary_response, visual_response=None):
    """Fake OpenAI boundary that dispatches on call shape: primary text calls
    use a plain string `input`; visual fallback calls use a list of content
    parts (see `documents.ai.classification.build_visual_request_parameters`).
    """
    calls = {"primary": [], "visual": []}

    def request(parameters):
        if isinstance(parameters["input"], str):
            calls["primary"].append(parameters)
            return primary_response()
        calls["visual"].append(parameters)
        return visual_response()

    return request, calls


BOL_LINES = [
    "BILL OF LADING",
    "CARRIER RECEIVED GOODS FOR TRANSPORT TO CONSIGNEE",
    "CARRIER ACME CONSIGNEE BETA CARGO WIDGETS WEIGHT 500 LB",
]
BOL_EVIDENCE = {
    "bol_identity": "BILL OF LADING",
    "bol_transport_obligation": "CARRIER RECEIVED GOODS FOR TRANSPORT TO CONSIGNEE",
    "bol_shipment_structure": "CARRIER ACME CONSIGNEE BETA CARGO WIDGETS WEIGHT 500 LB",
}

OTHER_LINES = [
    "COMMERCIAL INVOICE FOR GOODS",
    "PRODUCT QUANTITY HS CODE VALUE FOR CUSTOMS",
]
OTHER_EVIDENCE = {
    "non_target_identity": "COMMERCIAL INVOICE FOR GOODS",
    "non_target_primary_purpose": "PRODUCT QUANTITY HS CODE VALUE FOR CUSTOMS",
}

INVOICE_FRAGMENT_LINES = ["FREIGHT INVOICE FOR TRANSPORT SERVICES"]
INVOICE_FRAGMENT_EVIDENCE = {
    "transport_invoice_identity": "FREIGHT INVOICE FOR TRANSPORT SERVICES",
}


class PipelineTests(TestCase):
    def setUp(self) -> None:
        self.media_root = tempfile.mkdtemp()
        settings_override = override_settings(MEDIA_ROOT=self.media_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)

    def make_attempt(self, name: str, content: bytes) -> ProcessingAttempt:
        upload = SimpleUploadedFile(name, content, content_type="application/pdf")
        form = DocumentUploadForm(files={"document": upload})
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def test_accepted_bol(self) -> None:
        attempt = self.make_attempt("bol.pdf", make_text_pdf(BOL_LINES))
        observations = make_observations("BOL", BOL_EVIDENCE)
        calls = []

        def request(parameters):
            calls.append(parameters)
            return completed_response(observations)

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls), 1)
        self.assertEqual(result.status, ProcessingAttempt.Status.ACCEPTED)
        self.assertEqual(result.accepted_label, ProcessingAttempt.Label.BOL)
        self.assertEqual(result.routing_score, 1.0)
        self.assertEqual(result.score_method, "critical-feature-coverage-v1")
        self.assertEqual(result.primary_observations, observations)

    def test_accepted_other(self) -> None:
        attempt = self.make_attempt("other.pdf", make_text_pdf(OTHER_LINES))
        observations = make_observations("OTHER", OTHER_EVIDENCE)

        result = run_classification(
            attempt,
            request=lambda parameters: completed_response(observations),
        )

        self.assertEqual(result.status, ProcessingAttempt.Status.ACCEPTED)
        self.assertEqual(result.accepted_label, ProcessingAttempt.Label.OTHER)

    def test_incomplete_candidate_combination_is_uncertain_without_fallback(self) -> None:
        attempt = self.make_attempt(
            "fragment.pdf",
            make_text_pdf(INVOICE_FRAGMENT_LINES),
        )
        observations = make_observations("INVOICE", INVOICE_FRAGMENT_EVIDENCE)

        result = run_classification(
            attempt,
            request=lambda parameters: completed_response(observations),
        )

        self.assertEqual(result.status, ProcessingAttempt.Status.UNCERTAIN)
        self.assertIsNone(result.accepted_label)
        self.assertEqual(
            result.primary_metadata["routing"]["reason"],
            "incomplete_candidate_combination",
        )

    def test_no_extractable_text_skips_primary_and_tries_visual_fallback(self) -> None:
        # Neither native text nor OCR finds anything on this fixture (a blank
        # filled rectangle, no real content); production still gives the
        # visual fallback one chance, per the Task 5/G2 finding that vision
        # can succeed where OCR text is completely unusable.
        attempt = self.make_attempt("scan.pdf", make_image_only_pdf())
        visual_observations = make_observations("OTHER")
        request, calls = make_dual_request(
            lambda: (_ for _ in ()).throw(AssertionError("primary should not be called")),
            lambda: completed_response(visual_observations),
        )

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls["primary"]), 0)
        self.assertEqual(len(calls["visual"]), 1)
        self.assertEqual(result.status, ProcessingAttempt.Status.UNCERTAIN)
        self.assertIsNone(result.accepted_label)
        self.assertEqual(result.primary_metadata, {"skipped": True, "reason": "no_extractable_text"})
        self.assertEqual(result.fallback_observations, visual_observations)
        self.assertTrue(result.original_file.storage.exists(result.original_file.name))

    def test_no_extractable_text_and_render_failure_is_a_technical_failure(self) -> None:
        attempt = self.make_attempt("scan.pdf", make_image_only_pdf())

        with patch("documents.services.processing.render_all_pages", side_effect=RuntimeError("boom")):
            result = run_classification(
                attempt,
                request=lambda parameters: (_ for _ in ()).throw(
                    AssertionError("no call expected")
                ),
            )

        self.assertEqual(result.status, ProcessingAttempt.Status.FAILED)
        self.assertEqual(result.failure_stage, "visual_fallback")
        self.assertEqual(result.failure_category, "render_error")
        self.assertIsNone(result.accepted_label)

    def test_invalid_model_response_is_a_technical_failure_after_one_retry(self) -> None:
        attempt = self.make_attempt("bol.pdf", make_text_pdf(BOL_LINES))
        observations = make_observations(
            "BOL",
            {**BOL_EVIDENCE, "bol_identity": "not an exact quote"},
        )
        calls = []

        def request(parameters):
            calls.append(parameters)
            return completed_response(observations)

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls), 2)
        self.assertEqual(result.status, ProcessingAttempt.Status.FAILED)
        self.assertEqual(result.failure_stage, "classification")
        self.assertEqual(result.failure_category, "invalid_structured_output")
        self.assertIsNone(result.accepted_label)
        self.assertTrue(result.original_file.storage.exists(result.original_file.name))

    def test_api_timeout_is_a_technical_failure_after_one_retry(self) -> None:
        attempt = self.make_attempt("bol.pdf", make_text_pdf(BOL_LINES))
        calls = []

        def request(parameters):
            calls.append(parameters)
            raise RetryableRequestFailure("technical_failure")

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls), 2)
        self.assertEqual(result.status, ProcessingAttempt.Status.FAILED)
        self.assertEqual(result.failure_stage, "classification")
        self.assertEqual(result.failure_category, "technical_failure")
        self.assertIsNone(result.accepted_label)
        self.assertTrue(result.original_file.storage.exists(result.original_file.name))

    def test_non_retryable_configuration_failure_stops_after_one_call(self) -> None:
        attempt = self.make_attempt("bol.pdf", make_text_pdf(BOL_LINES))
        calls = []

        def request(parameters):
            calls.append(parameters)
            raise NonRetryableRequestFailure("configuration_failure")

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls), 1)
        self.assertEqual(result.status, ProcessingAttempt.Status.FAILED)
        self.assertEqual(result.failure_category, "configuration_failure")

    # --- Visual fallback (Task 6) ---

    def test_accepted_primary_does_not_trigger_visual_fallback(self) -> None:
        attempt = self.make_attempt("bol.pdf", make_text_pdf(BOL_LINES))
        observations = make_observations("BOL", BOL_EVIDENCE)
        request, calls = make_dual_request(lambda: completed_response(observations))

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls["primary"]), 1)
        self.assertEqual(len(calls["visual"]), 0)
        self.assertEqual(result.status, ProcessingAttempt.Status.ACCEPTED)
        self.assertIsNone(result.fallback_observations)

    def test_established_ambiguity_does_not_trigger_visual_fallback(self) -> None:
        combined_lines = [
            *BOL_LINES,
            "PROOF OF DELIVERY",
            "DELIVERED",
            "SIGNED",
        ]
        attempt = self.make_attempt("combined.pdf", make_text_pdf(combined_lines))
        observations = make_observations(
            "BOL",
            {
                **BOL_EVIDENCE,
                "pod_identity": "PROOF OF DELIVERY",
                "completed_delivery_event": "DELIVERED",
                "recipient_acknowledgement": "SIGNED",
            },
        )
        request, calls = make_dual_request(lambda: completed_response(observations))

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls["visual"]), 0)
        self.assertEqual(result.status, ProcessingAttempt.Status.UNCERTAIN)
        self.assertIsNone(result.accepted_label)
        self.assertIsNone(result.fallback_observations)

    def test_incomplete_primary_escalates_to_visual_fallback_which_accepts(self) -> None:
        attempt = self.make_attempt(
            "fragment.pdf",
            make_text_pdf(INVOICE_FRAGMENT_LINES),
        )
        primary_observations = make_observations("INVOICE", INVOICE_FRAGMENT_EVIDENCE)
        visual_observations = make_observations(
            "BOL",
            evidence_by_feature={
                "bol_identity": "heading reads BILL OF LADING",
                "bol_transport_obligation": "carrier received goods for transport",
                "bol_shipment_structure": "lists shipper, consignee, carrier, cargo",
            },
        )
        request, calls = make_dual_request(
            lambda: completed_response(primary_observations),
            lambda: completed_response(visual_observations),
        )

        result = run_classification(attempt, request=request)

        self.assertEqual(len(calls["primary"]), 1)
        self.assertEqual(len(calls["visual"]), 1)
        # one input_text part plus one input_image part per page (1 page here)
        self.assertEqual(len(calls["visual"][0]["input"][0]["content"]), 2)
        self.assertEqual(result.status, ProcessingAttempt.Status.ACCEPTED)
        self.assertEqual(result.accepted_label, ProcessingAttempt.Label.BOL)
        self.assertEqual(result.primary_observations, primary_observations)
        self.assertEqual(result.fallback_observations, visual_observations)
        self.assertEqual(result.fallback_metadata["routing"]["action"], "ACCEPT")

    def test_visual_fallback_incomplete_result_is_uncertain(self) -> None:
        attempt = self.make_attempt(
            "fragment.pdf",
            make_text_pdf(INVOICE_FRAGMENT_LINES),
        )
        primary_observations = make_observations("INVOICE", INVOICE_FRAGMENT_EVIDENCE)
        visual_observations = make_observations("INVOICE")
        request, calls = make_dual_request(
            lambda: completed_response(primary_observations),
            lambda: completed_response(visual_observations),
        )

        result = run_classification(attempt, request=request)

        self.assertEqual(result.status, ProcessingAttempt.Status.UNCERTAIN)
        self.assertIsNone(result.accepted_label)
        self.assertEqual(result.fallback_observations, visual_observations)

    def test_visual_fallback_technical_failure_preserves_primary_diagnostics(self) -> None:
        attempt = self.make_attempt(
            "fragment.pdf",
            make_text_pdf(INVOICE_FRAGMENT_LINES),
        )
        primary_observations = make_observations("INVOICE", INVOICE_FRAGMENT_EVIDENCE)
        calls = {"primary": 0, "visual": 0}

        def request(parameters):
            if isinstance(parameters["input"], str):
                calls["primary"] += 1
                return completed_response(primary_observations)
            calls["visual"] += 1
            raise RetryableRequestFailure("technical_failure")

        result = run_classification(attempt, request=request)

        self.assertEqual(calls["primary"], 1)
        self.assertEqual(calls["visual"], 2)  # one retry, per the agreed policy
        self.assertEqual(result.status, ProcessingAttempt.Status.FAILED)
        self.assertEqual(result.failure_stage, "visual_fallback")
        self.assertEqual(result.failure_category, "technical_failure")
        self.assertIsNone(result.accepted_label)
        # Task 6 requirement: fallback failure preserves the primary result for diagnostics.
        self.assertEqual(result.primary_observations, primary_observations)
        self.assertIsNotNone(result.primary_metadata)


EVALUATION_DOCUMENTS = Path(__file__).resolve().parent.parent.parent / "evaluation" / "documents"


class RealPdfOcrTests(unittest.TestCase):
    """Real-parser/OCR checks on actual PDF fixtures (no fakes, no API calls),
    per the Task 6 checklist: verifies documents.services.pdf.extract_text on
    genuine text-layer and scanned files, reusing the Task 5/G2 fixture set.
    """

    def test_native_text_layer_pdf_extracts_correctly(self) -> None:
        with (EVALUATION_DOCUMENTS / "v2-heldout-invoice-forwarder.pdf").open("rb") as pdf_file:
            text = extract_text(pdf_file)

        self.assertIn("FREIGHT FORWARDER INVOICE", text)

    def test_clean_scanned_pdf_extracts_via_ocr(self) -> None:
        with (EVALUATION_DOCUMENTS / "scan-bol-rail.pdf").open("rb") as pdf_file:
            text = extract_text(pdf_file)

        self.assertIn("RAIL BILL OF LADING", text)

    def test_stray_text_over_image_uses_the_image_content_not_the_stamp(self) -> None:
        with (EVALUATION_DOCUMENTS / "scan-stray-text-over-image-bol-rail.pdf").open(
            "rb"
        ) as pdf_file:
            text = extract_text(pdf_file)

        self.assertIn("RAIL BILL OF LADING", text)

    def test_severely_degraded_scan_yields_no_usable_text(self) -> None:
        with (EVALUATION_DOCUMENTS / "scan-severely-degraded-bol-rail.pdf").open(
            "rb"
        ) as pdf_file:
            text = extract_text(pdf_file)

        self.assertEqual(text.strip(), "")
