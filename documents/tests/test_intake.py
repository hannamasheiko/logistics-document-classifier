import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from documents.forms import DocumentUploadForm
from documents.models import ProcessingAttempt
from documents.services.pdf import MAX_PDF_BYTES


def make_pdf(page_count: int = 1, *, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    if encrypted:
        writer.encrypt("secret")
    content = BytesIO()
    writer.write(content)
    return content.getvalue()


def make_image_only_pdf() -> bytes:
    content = BytesIO()
    page = canvas.Canvas(content, pagesize=(100, 100))
    page.drawInlineImage(Image.new("RGB", (10, 10), "white"), 10, 10, 80, 80)
    page.showPage()
    page.save()
    return content.getvalue()


class IntakeTests(TestCase):
    def setUp(self) -> None:
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()

    def tearDown(self) -> None:
        self.settings_override.disable()
        shutil.rmtree(self.media_root)

    def submit(
        self,
        name: str,
        content: bytes,
        *,
        content_type: str = "application/pdf",
    ) -> DocumentUploadForm:
        upload = SimpleUploadedFile(name, content, content_type=content_type)
        form = DocumentUploadForm(files={"document": upload})
        if form.is_valid():
            form.save()
        return form

    def assert_no_attempt_or_media(self) -> None:
        self.assertEqual(ProcessingAttempt.objects.count(), 0)
        self.assertEqual(list(Path(self.media_root).rglob("*")), [])

    def test_rejects_eleven_page_pdf_before_creating_attempt(self) -> None:
        form = self.submit("eleven-pages.pdf", make_pdf(page_count=11))

        self.assertFalse(form.is_valid())
        self.assertIn("at most 10 pages", form.errors["document"][0])
        self.assert_no_attempt_or_media()

    def test_rejects_upload_over_exact_byte_limit(self) -> None:
        oversized = b"%PDF-1.4\n" + b"0" * MAX_PDF_BYTES

        form = self.submit("oversized.pdf", oversized)

        self.assertFalse(form.is_valid())
        self.assertIn("10,000,000 bytes", form.errors["document"][0])
        self.assert_no_attempt_or_media()

    def test_rejects_non_pdf_renamed_with_pdf_extension(self) -> None:
        form = self.submit("renamed.pdf", b"This is not a PDF.")

        self.assertFalse(form.is_valid())
        self.assertIn("valid PDF", form.errors["document"][0])
        self.assert_no_attempt_or_media()

    def test_rejects_encrypted_pdf(self) -> None:
        form = self.submit("encrypted.pdf", make_pdf(encrypted=True))

        self.assertFalse(form.is_valid())
        self.assertIn("Encrypted PDFs", form.errors["document"][0])
        self.assert_no_attempt_or_media()

    def test_accepts_image_only_pdf_at_intake(self) -> None:
        content = make_image_only_pdf()
        self.assertEqual(PdfReader(BytesIO(content)).pages[0].extract_text(), "")

        form = self.submit("scan.pdf", content)

        self.assertTrue(form.is_valid(), form.errors)
        attempt = ProcessingAttempt.objects.get()
        self.assertEqual(attempt.status, ProcessingAttempt.Status.PROCESSING)
        self.assertEqual(attempt.page_count, 1)
        self.assertEqual(attempt.size_bytes, len(content))
        self.assertTrue(attempt.original_file.storage.exists(attempt.original_file.name))

    def test_accepts_valid_pdf_with_generic_mime_type(self) -> None:
        form = self.submit(
            "document.pdf",
            make_pdf(),
            content_type="application/octet-stream",
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(ProcessingAttempt.objects.count(), 1)

    def test_repeat_upload_creates_distinct_attempts_and_files(self) -> None:
        content = make_pdf()

        first_form = self.submit("document.pdf", content)
        second_form = self.submit("document.pdf", content)

        self.assertTrue(first_form.is_valid(), first_form.errors)
        self.assertTrue(second_form.is_valid(), second_form.errors)
        attempts = list(ProcessingAttempt.objects.order_by("created_at"))
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(attempts[0].pk, attempts[1].pk)
        self.assertNotEqual(
            attempts[0].original_file.name,
            attempts[1].original_file.name,
        )
        for attempt in attempts:
            with attempt.original_file.open("rb") as stored:
                self.assertEqual(PdfReader(stored).get_num_pages(), 1)

    def test_failure_after_intake_retains_attempt_and_original(self) -> None:
        form = self.submit("document.pdf", make_pdf())
        attempt = ProcessingAttempt.objects.get()

        attempt.status = ProcessingAttempt.Status.FAILED
        attempt.failure_stage = "text_extraction"
        attempt.failure_category = "parser_error"
        attempt.failure_reason = "Text extraction failed."
        attempt.save()

        attempt.refresh_from_db()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(attempt.status, ProcessingAttempt.Status.FAILED)
        self.assertIsNone(attempt.accepted_label)
        self.assertTrue(attempt.original_file.storage.exists(attempt.original_file.name))

    def test_accepted_status_requires_final_label(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProcessingAttempt.objects.create(
                original_file="documents/missing.pdf",
                original_name="missing.pdf",
                size_bytes=100,
                page_count=1,
                status=ProcessingAttempt.Status.ACCEPTED,
                accepted_label=None,
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            ProcessingAttempt.objects.create(
                original_file="documents/missing.pdf",
                original_name="missing.pdf",
                size_bytes=100,
                page_count=1,
                status=ProcessingAttempt.Status.PROCESSING,
                accepted_label=ProcessingAttempt.Label.BOL,
            )
