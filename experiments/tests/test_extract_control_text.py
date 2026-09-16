import json
import tempfile
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas

from experiments.extract_control_text import extract_document, redact_sensitive_values, write_jsonl


class ExtractControlTextTests(unittest.TestCase):
    def test_extract_document_preserves_page_boundaries_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "sample.pdf"
            pdf = canvas.Canvas(str(pdf_path))
            pdf.drawString(72, 720, "First page text")
            pdf.showPage()
            pdf.drawString(72, 720, "Second page text")
            pdf.save()

            result = extract_document(pdf_path, "BOL")

            self.assertEqual(result["source_file"], "sample.pdf")
            self.assertEqual(result["expected_class"], "BOL")
            self.assertEqual(result["page_count"], 2)
            self.assertEqual(result["pages"], ["First page text", "Second page text"])
            self.assertEqual(result["character_count"], 31)

    def test_write_jsonl_writes_one_unicode_record_per_line(self):
        records = [
            {
                "source_file": "pod.pdf",
                "expected_class": "POD",
                "page_count": 1,
                "character_count": 8,
                "pages": ["Доставлено"],
            },
            {
                "source_file": "invoice.pdf",
                "expected_class": "INVOICE",
                "page_count": 1,
                "character_count": 7,
                "pages": ["Invoice"],
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "controls.jsonl"
            write_jsonl(records, output_path)

            lines = output_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0]), records[0])
        self.assertEqual(json.loads(lines[1]), records[1])
        self.assertIn("Доставлено", lines[0])

    def test_redact_sensitive_values_masks_payment_identifiers(self):
        text = (
            "Account Number (Account #): ACCOUNT_VALUE\n"
            "Routing Number (ABA / ACH): ROUTING_VALUE\n"
            "SWIFT / BIC Code: SWIFT_VALUE\n"
            "Invoice Number: INV-2026-8841"
        )

        redacted = redact_sensitive_values(text)

        self.assertEqual(
            redacted,
            "Account Number (Account #): [REDACTED]\n"
            "Routing Number (ABA / ACH): [REDACTED]\n"
            "SWIFT / BIC Code: [REDACTED]\n"
            "Invoice Number: INV-2026-8841",
        )


if __name__ == "__main__":
    unittest.main()
