import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader


SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?im)^(Account Number(?:\s*\([^)]*\))?\s*:\s*)\S+"),
    re.compile(r"(?im)^(Routing Number(?:\s*\([^)]*\))?\s*:\s*)\S+"),
    re.compile(r"(?im)^(SWIFT(?:\s*/\s*BIC)?(?:\s+Code)?\s*:\s*)\S+"),
    re.compile(r"(?i)(AC NO\s*:\s*)\S+"),
    re.compile(r"(?i)(SWIFT CODE\s*:\s*)\S+"),
)


def redact_sensitive_values(text: str) -> str:
    for pattern in SENSITIVE_VALUE_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


def extract_document(pdf_path: Path, expected_class: str) -> dict:
    reader = PdfReader(pdf_path)
    pages = [
        redact_sensitive_values((page.extract_text() or "").strip())
        for page in reader.pages
    ]

    return {
        "source_file": pdf_path.name,
        "expected_class": expected_class,
        "page_count": len(pages),
        "character_count": sum(len(page) for page in pages),
        "pages": pages,
    }


def write_jsonl(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        for record in records
    )
    output_path.write_text(f"{content}\n", encoding="utf-8")


def parse_document(value: str) -> tuple[str, Path]:
    try:
        expected_class, path = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use EXPECTED_CLASS=/path/to/file.pdf") from error
    return expected_class, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from control PDFs.")
    parser.add_argument(
        "--document",
        action="append",
        required=True,
        type=parse_document,
        metavar="EXPECTED_CLASS=PDF_PATH",
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()

    records = [extract_document(path, label) for label, path in arguments.document]
    write_jsonl(records, arguments.output)


if __name__ == "__main__":
    main()
