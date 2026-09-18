import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from documents.ai.classification import RetryableRequestFailure
from documents.models import ProcessingAttempt
from documents.tests.test_pipeline import (
    BOL_EVIDENCE,
    BOL_LINES,
    INVOICE_FRAGMENT_EVIDENCE,
    INVOICE_FRAGMENT_LINES,
    OTHER_EVIDENCE,
    OTHER_LINES,
    completed_response,
    default_extraction_payload,
    make_dual_request,
    make_image_only_pdf,
    make_observations,
    make_text_pdf,
)


class ViewTests(TestCase):
    def setUp(self) -> None:
        self.media_root = tempfile.mkdtemp()
        settings_override = override_settings(MEDIA_ROOT=self.media_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)

    def upload(self, name: str, content: bytes):
        upload = SimpleUploadedFile(name, content, content_type="application/pdf")
        return self.client.post(
            reverse("documents:upload"),
            {"document": upload},
            follow=True,
        )

    def test_valid_upload_creates_attempt_and_redirects_to_result(self) -> None:
        observations = make_observations("OTHER", OTHER_EVIDENCE)
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = lambda parameters: completed_response(observations)
            response = self.upload("other.pdf", make_text_pdf(OTHER_LINES))

        self.assertEqual(response.status_code, 200)
        attempt = ProcessingAttempt.objects.get()
        self.assertRedirects(
            response,
            reverse("documents:result", args=[attempt.pk]),
        )
        self.assertEqual(attempt.status, ProcessingAttempt.Status.ACCEPTED)
        self.assertContains(response, "Accepted label")
        self.assertContains(response, "Other")

    def test_invalid_upload_does_not_create_attempt(self) -> None:
        response = self.client.post(
            reverse("documents:upload"),
            {"document": SimpleUploadedFile("renamed.pdf", b"not a pdf")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProcessingAttempt.objects.count(), 0)
        self.assertContains(response, "valid PDF")

    def test_history_lists_multiple_attempts_of_the_same_pdf(self) -> None:
        content = make_text_pdf(OTHER_LINES)
        observations = make_observations("OTHER", OTHER_EVIDENCE)
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = lambda parameters: completed_response(observations)
            self.upload("document.pdf", content)
            self.upload("document.pdf", content)

        attempts = list(ProcessingAttempt.objects.order_by("pk"))
        self.assertEqual(len(attempts), 2)

        response = self.client.get(reverse("documents:history"))

        self.assertEqual(response.status_code, 200)
        for attempt in attempts:
            self.assertContains(
                response,
                reverse("documents:result", args=[attempt.pk]),
            )

    def test_uncertain_result_is_not_displayed_as_accepted(self) -> None:
        observations = make_observations("INVOICE", INVOICE_FRAGMENT_EVIDENCE)
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = lambda parameters: completed_response(observations)
            response = self.upload("fragment.pdf", make_text_pdf(INVOICE_FRAGMENT_LINES))

        attempt = ProcessingAttempt.objects.get()
        self.assertEqual(attempt.status, ProcessingAttempt.Status.UNCERTAIN)
        self.assertIsNone(attempt.accepted_label)
        self.assertNotContains(response, "Accepted label")
        self.assertContains(response, "could not be classified")

    def test_failed_result_is_not_displayed_as_accepted(self) -> None:
        # No extractable text (native or OCR) still tries the visual
        # fallback once (Task 5/G2); make that fallback call itself
        # technically fail so the attempt ends as a real FAILED example.
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = lambda parameters: (_ for _ in ()).throw(
                RetryableRequestFailure("technical_failure")
            )
            response = self.upload("scan.pdf", make_image_only_pdf())

        attempt = ProcessingAttempt.objects.get()
        self.assertEqual(attempt.status, ProcessingAttempt.Status.FAILED)
        self.assertEqual(attempt.failure_stage, "visual_fallback")
        self.assertIsNone(attempt.accepted_label)
        self.assertNotContains(response, "Accepted label")
        self.assertContains(response, "Processing failed")

    def test_original_pdf_is_served_by_record_reference(self) -> None:
        content = make_text_pdf(OTHER_LINES)
        observations = make_observations("OTHER", OTHER_EVIDENCE)
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = lambda parameters: completed_response(observations)
            self.upload("other.pdf", content)

        attempt = ProcessingAttempt.objects.get()
        response = self.client.get(reverse("documents:original", args=[attempt.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(b"".join(response.streaming_content), content)

    def test_unknown_attempt_original_returns_not_found(self) -> None:
        response = self.client.get(reverse("documents:original", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_unknown_attempt_result_returns_not_found(self) -> None:
        response = self.client.get(reverse("documents:result", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_visual_fallback_accept_is_shown_on_the_result_page(self) -> None:
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
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = request
            response = self.upload("fragment.pdf", make_text_pdf(INVOICE_FRAGMENT_LINES))

        self.assertEqual(len(calls["primary"]), 1)
        self.assertEqual(len(calls["visual"]), 1)
        attempt = ProcessingAttempt.objects.get()
        self.assertEqual(attempt.status, ProcessingAttempt.Status.ACCEPTED)
        self.assertEqual(attempt.accepted_label, ProcessingAttempt.Label.BOL)
        self.assertContains(response, "Accepted label")
        self.assertContains(response, "Bill of lading")

    def test_extracted_fields_table_is_shown_on_the_result_page(self) -> None:
        observations = make_observations("BOL", BOL_EVIDENCE)
        extraction_payload = {
            **default_extraction_payload("BOL"),
            "bol_number": {"status": "present", "value": "RBL-20773", "evidence": "BILL OF LADING"},
        }
        request, calls = make_dual_request(
            lambda: completed_response(observations),
            extraction_response=lambda class_name: completed_response(extraction_payload),
        )
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = request
            response = self.upload("bol.pdf", make_text_pdf(BOL_LINES))

        self.assertEqual(len(calls["extraction"]), 1)
        self.assertContains(response, "Extracted fields")
        self.assertContains(response, "RBL-20773")
        self.assertContains(response, "bol_number")

    def test_extraction_failure_note_is_shown_without_fake_field_values(self) -> None:
        observations = make_observations("BOL", BOL_EVIDENCE)

        def extraction_response(class_name):
            raise RetryableRequestFailure("technical_failure")

        request, calls = make_dual_request(
            lambda: completed_response(observations),
            extraction_response=extraction_response,
        )
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = request
            response = self.upload("bol.pdf", make_text_pdf(BOL_LINES))

        attempt = ProcessingAttempt.objects.get()
        self.assertEqual(attempt.status, ProcessingAttempt.Status.ACCEPTED)
        self.assertContains(response, "Field extraction technically failed")
        self.assertNotContains(response, "Extracted fields")

    def test_extracted_fields_and_original_survive_reopening_the_result_page(self) -> None:
        # Confirms persistence, not just the response from the upload request:
        # a fresh GET (a separate request/response cycle) must show the same
        # fields, and the original PDF link must still resolve, from history.
        observations = make_observations("BOL", BOL_EVIDENCE)
        extraction_payload = {
            **default_extraction_payload("BOL"),
            "bol_number": {"status": "present", "value": "RBL-20773", "evidence": "BILL OF LADING"},
        }
        request, _calls = make_dual_request(
            lambda: completed_response(observations),
            extraction_response=lambda class_name: completed_response(extraction_payload),
        )
        with patch("documents.services.processing.build_default_request") as mock_build:
            mock_build.return_value = request
            self.upload("bol.pdf", make_text_pdf(BOL_LINES))

        attempt = ProcessingAttempt.objects.get()
        reopened = self.client.get(reverse("documents:result", args=[attempt.pk]))

        self.assertContains(reopened, "Extracted fields")
        self.assertContains(reopened, "RBL-20773")
        self.assertContains(reopened, reverse("documents:original", args=[attempt.pk]))

        original_response = self.client.get(reverse("documents:original", args=[attempt.pk]))
        self.assertEqual(original_response.status_code, 200)
