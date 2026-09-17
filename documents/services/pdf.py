from dataclasses import dataclass

from pypdf import PdfReader


MAX_PDF_BYTES = 10_000_000
MAX_PDF_PAGES = 10


class PDFValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PDFInspection:
    size_bytes: int
    page_count: int


def inspect_pdf(uploaded_file) -> PDFInspection:
    size_bytes = uploaded_file.size
    if size_bytes > MAX_PDF_BYTES:
        raise PDFValidationError(
            "file_too_large",
            "PDF must be at most 10,000,000 bytes.",
        )

    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(1024)
        uploaded_file.seek(0)
        if b"%PDF-" not in header:
            raise PDFValidationError("invalid_pdf", "Upload must be a valid PDF.")

        reader = PdfReader(uploaded_file, strict=False)
        if reader.is_encrypted:
            raise PDFValidationError(
                "encrypted_pdf",
                "Encrypted PDFs are not supported.",
            )

        page_count = len(reader.pages)
        if page_count == 0:
            raise PDFValidationError(
                "empty_pdf",
                "PDF must contain at least one page.",
            )
        if page_count > MAX_PDF_PAGES:
            raise PDFValidationError(
                "too_many_pages",
                "PDF must contain at most 10 pages.",
            )
        return PDFInspection(size_bytes=size_bytes, page_count=page_count)
    except PDFValidationError:
        raise
    except Exception as error:
        raise PDFValidationError("invalid_pdf", "Upload must be a valid PDF.") from error
    finally:
        uploaded_file.seek(0)
