from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from pypdf import PdfReader

from documents.services.ocr import extract_text_from_image


MAX_PDF_BYTES = 10_000_000
MAX_PDF_PAGES = 10
RENDER_SCALE = 200 / 72  # ~200 DPI; matches the Task 5/G2 feasibility experiment.


class PDFValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PDFInspection:
    size_bytes: int
    page_count: int


def render_page_to_image(pdf_bytes: bytes, page_index: int):
    with pdfium.PdfDocument(pdf_bytes) as document:
        page = document[page_index]
        try:
            return page.render(scale=RENDER_SCALE).to_pil()
        finally:
            page.close()


def render_all_pages(pdf_bytes: bytes) -> list:
    with pdfium.PdfDocument(pdf_bytes) as document:
        images = []
        for page in document:
            try:
                images.append(page.render(scale=RENDER_SCALE).to_pil())
            finally:
                page.close()
        return images


def extract_text(pdf_file) -> str:
    """Effective per-page text, joined page by page.

    Task 5/G2 agreed text-sufficiency policy: use native pypdf text unless
    local OCR of the rendered page is strictly longer (non-whitespace
    character count), in which case use the OCR text. OCR runs on every page
    (local, no per-call cost) rather than relying on a length threshold: a
    fixed threshold was proposed and found unsafe during the G2 experiment
    (see docs/experiments/scanned-fallback.md). Callers are expected to have
    passed the file through `inspect_pdf` at intake, so page count/encryption
    are not re-checked here.
    """
    content = pdf_file.read()
    reader = PdfReader(BytesIO(content), strict=False)
    pages = []
    with pdfium.PdfDocument(content) as document:
        for index, page_reader in enumerate(reader.pages):
            native_text = (page_reader.extract_text() or "").strip()
            pdfium_page = document[index]
            try:
                image = pdfium_page.render(scale=RENDER_SCALE).to_pil()
            finally:
                pdfium_page.close()
            ocr_text = extract_text_from_image(image)
            native_length = len("".join(native_text.split()))
            ocr_length = len("".join(ocr_text.split()))
            pages.append(ocr_text if ocr_length > native_length else native_text)
    return "\n\n".join(pages)


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
