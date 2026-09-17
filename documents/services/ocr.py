"""Local OCR: image -> text.

Isolated in its own module so an OCR engine failure is a distinct, catchable
technical failure category (Task 5/G2), never silently treated as semantic
uncertainty or OTHER.
"""

import pytesseract
from PIL import Image


class OCRError(Exception):
    """Raised when local OCR fails; callers must treat this as a technical failure."""


def extract_text_from_image(image: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception as error:
        raise OCRError("Local OCR failed.") from error
