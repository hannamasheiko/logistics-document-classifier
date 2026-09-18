from pathlib import Path

from django import forms

from documents.models import ProcessingAttempt
from documents.services.pdf import PDFValidationError, inspect_pdf


class DocumentUploadForm(forms.Form):
    document = forms.FileField(
        label="PDF document",
        help_text="At most 10 pages and 10,000,000 bytes.",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,application/pdf"}),
    )

    def clean_document(self):
        uploaded_file = self.cleaned_data["document"]
        try:
            self.pdf_inspection = inspect_pdf(uploaded_file)
        except PDFValidationError as error:
            raise forms.ValidationError(str(error), code=error.code) from error
        return uploaded_file

    def save(self) -> ProcessingAttempt:
        if not self.is_valid():
            raise ValueError("Cannot save an invalid upload form.")

        uploaded_file = self.cleaned_data["document"]
        attempt = ProcessingAttempt(
            original_file=uploaded_file,
            original_name=Path(uploaded_file.name).name,
            size_bytes=self.pdf_inspection.size_bytes,
            page_count=self.pdf_inspection.page_count,
            status=ProcessingAttempt.Status.PROCESSING,
        )
        try:
            attempt.save()
        except Exception:
            if attempt.original_file.name:
                attempt.original_file.storage.delete(attempt.original_file.name)
            raise
        return attempt
