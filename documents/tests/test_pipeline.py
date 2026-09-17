import json
import shutil
import tempfile
from io import BytesIO

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

    def test_extraction_failure_on_text_less_pdf_does_not_call_model(self) -> None:
        attempt = self.make_attempt("scan.pdf", make_image_only_pdf())
        calls = []

        result = run_classification(attempt, request=lambda parameters: calls.append(parameters))

        self.assertEqual(calls, [])
        self.assertEqual(result.status, ProcessingAttempt.Status.FAILED)
        self.assertEqual(result.failure_stage, "text_extraction")
        self.assertIsNone(result.accepted_label)
        self.assertTrue(result.original_file.storage.exists(result.original_file.name))

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
