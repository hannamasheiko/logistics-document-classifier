import json
import unittest

from documents.ai.classification import NonRetryableRequestFailure, RetryableRequestFailure
from documents.ai.extraction import (
    ExtractionFailure,
    ExtractionOutputValidationError,
    FIELD_DEFINITIONS,
    build_extraction_text_format,
    compute_field_confidence,
    enrich_fields,
    extract_fields,
    find_contradictions,
    validate_amount,
    validate_date,
    validate_extraction_output,
    validate_identifier,
)


def make_payload(class_name, present=None):
    """Build a full valid extraction payload for `class_name` with every
    field `missing` except those given a (value, evidence) pair in `present`.
    """
    present = present or {}
    payload = {}
    for field_name in FIELD_DEFINITIONS[class_name]:
        if field_name in present:
            value, evidence = present[field_name]
            payload[field_name] = {"status": "present", "value": value, "evidence": evidence}
        else:
            payload[field_name] = {"status": "missing", "value": None, "evidence": None}
    return payload


class ValidatorTests(unittest.TestCase):
    def test_validate_date_accepts_common_formats_and_ignores_trailing_time(self):
        self.assertTrue(validate_date("2026-09-04")["valid"])
        self.assertTrue(validate_date("09/04/2026")["valid"])
        result = validate_date("September 4, 2026 at 10:18 EDT")
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized_value"], "2026-09-04")

    def test_validate_date_rejects_payment_terms(self):
        result = validate_date("Net 21")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "no_parseable_date_found")

    def test_validate_amount_parses_currency_string(self):
        result = validate_amount("$2,180.00")
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized_value"], "2180.00")

    def test_validate_amount_rejects_non_numeric_text(self):
        result = validate_amount("payment due on receipt")
        self.assertFalse(result["valid"])

    def test_validate_identifier_accepts_short_mixed_alnum_values(self):
        self.assertTrue(validate_identifier("RBL-20773")["valid"])
        self.assertTrue(validate_identifier("SFR-88341")["valid"])

    def test_validate_identifier_rejects_implausibly_long_text(self):
        result = validate_identifier("x" * 60)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "implausibly_long")


class ContradictionAndConfidenceTests(unittest.TestCase):
    def test_identical_shipper_and_consignee_is_flagged_both_ways(self):
        payload = make_payload(
            "BOL",
            present={
                "shipper": ("Meridian Freight Solutions, Dallas, TX", "..."),
                "consignee": ("Meridian Freight Solutions, Dallas, TX", "..."),
            },
        )
        contradictions = find_contradictions(payload, "BOL")
        self.assertEqual(contradictions["shipper"], ["consignee"])
        self.assertEqual(contradictions["consignee"], ["shipper"])

    def test_different_shipper_and_consignee_has_no_contradiction(self):
        payload = make_payload(
            "BOL",
            present={
                "shipper": ("Prairie Grain Cooperative, Omaha, NE", "..."),
                "consignee": ("Riverbend Milling, St. Louis, MO", "..."),
            },
        )
        self.assertEqual(find_contradictions(payload, "BOL"), {})

    def test_provider_equals_bill_to_is_flagged_on_invoice(self):
        payload = make_payload(
            "INVOICE",
            present={
                "provider": ("Acme Logistics", "..."),
                "bill_to": ("Acme Logistics", "..."),
            },
        )
        contradictions = find_contradictions(payload, "INVOICE")
        self.assertEqual(contradictions["provider"], ["bill_to"])

    def test_pod_has_no_consistency_pairs(self):
        payload = make_payload("POD")
        self.assertEqual(find_contradictions(payload, "POD"), {})

    def test_confidence_levels(self):
        self.assertIsNone(compute_field_confidence("missing", None, False))
        self.assertIsNone(compute_field_confidence("unclear", None, False))
        self.assertEqual(compute_field_confidence("present", None, True), 0.0)
        self.assertEqual(
            compute_field_confidence("present", {"valid": False}, False),
            0.5,
        )
        self.assertEqual(compute_field_confidence("present", {"valid": True}, False), 1.0)
        self.assertEqual(compute_field_confidence("present", None, False), 1.0)

    def test_enrich_fields_keeps_both_contradicting_values_and_zeroes_both(self):
        payload = make_payload(
            "BOL",
            present={
                "bol_number": ("BOL-40217", "BOL No: BOL-40217"),
                "shipper": ("Meridian Freight Solutions, Dallas, TX", "..."),
                "consignee": ("Meridian Freight Solutions, Dallas, TX", "..."),
            },
        )
        enriched = enrich_fields(payload, "BOL")

        self.assertEqual(enriched["shipper"]["value"], "Meridian Freight Solutions, Dallas, TX")
        self.assertEqual(enriched["consignee"]["value"], "Meridian Freight Solutions, Dallas, TX")
        self.assertEqual(enriched["shipper"]["confidence"], 0.0)
        self.assertEqual(enriched["consignee"]["confidence"], 0.0)
        self.assertEqual(enriched["shipper"]["contradiction_with"], ["consignee"])
        self.assertEqual(enriched["bol_number"]["confidence"], 1.0)


class ValidateExtractionOutputTests(unittest.TestCase):
    def test_valid_payload_with_text_evidence_passes(self):
        payload = make_payload(
            "INVOICE",
            present={"invoice_number": ("FFI-19024", "Invoice: FFI-19024")},
        )
        validate_extraction_output(
            payload,
            "INVOICE",
            document_text="FREIGHT FORWARDER INVOICE\nInvoice: FFI-19024",
        )

    def test_evidence_not_in_source_text_is_rejected(self):
        payload = make_payload(
            "INVOICE",
            present={"invoice_number": ("FFI-19024", "not in the source")},
        )
        with self.assertRaises(ExtractionOutputValidationError) as raised:
            validate_extraction_output(payload, "INVOICE", document_text="FFI-19024 only")
        self.assertEqual(raised.exception.code, "evidence_not_exact_substring")

    def test_visual_context_skips_exact_substring_check(self):
        payload = make_payload(
            "INVOICE",
            present={"invoice_number": ("FFI-19024", "top-right corner reads FFI-19024")},
        )
        validate_extraction_output(payload, "INVOICE", document_text=None)

    def test_present_status_requires_non_null_value_and_evidence(self):
        payload = make_payload("INVOICE")
        payload["invoice_number"] = {"status": "present", "value": None, "evidence": None}
        with self.assertRaises(ExtractionOutputValidationError) as raised:
            validate_extraction_output(payload, "INVOICE", document_text="anything")
        self.assertEqual(raised.exception.code, "missing_present_value")

    def test_missing_status_requires_null_value_and_evidence(self):
        payload = make_payload("INVOICE")
        payload["invoice_number"] = {"status": "missing", "value": "FFI-19024", "evidence": "x"}
        with self.assertRaises(ExtractionOutputValidationError) as raised:
            validate_extraction_output(payload, "INVOICE", document_text="anything")
        self.assertEqual(raised.exception.code, "non_null_inactive_value_or_evidence")

    def test_unexpected_field_set_is_rejected(self):
        payload = make_payload("INVOICE")
        del payload["invoice_number"]
        with self.assertRaises(ExtractionOutputValidationError) as raised:
            validate_extraction_output(payload, "INVOICE", document_text="anything")
        self.assertEqual(raised.exception.code, "unexpected_root_fields")


class SchemaTests(unittest.TestCase):
    def test_text_format_is_strict_and_matches_field_definitions(self):
        schema = build_extraction_text_format("BOL")
        self.assertTrue(schema["strict"])
        self.assertEqual(
            set(schema["schema"]["properties"]),
            set(FIELD_DEFINITIONS["BOL"]),
        )
        self.assertFalse(schema["schema"]["additionalProperties"])


def completed_response(payload: dict) -> dict:
    return {
        "response_id": "response-1",
        "status": "completed",
        "output_text": json.dumps(payload),
        "usage": {"input_tokens": 100, "output_tokens": 50, "reasoning_tokens": 10},
        "latency_seconds": 0.2,
    }


class ExtractFieldsTests(unittest.TestCase):
    def test_extract_fields_from_text_context(self):
        document_text = "RAIL BILL OF LADING\nRail B/L: RBL-20773\nShipper: Prairie Grain Cooperative, Omaha, NE"
        payload = make_payload(
            "BOL",
            present={
                "bol_number": ("RBL-20773", "Rail B/L: RBL-20773"),
                "shipper": ("Prairie Grain Cooperative, Omaha, NE", "Shipper: Prairie Grain Cooperative, Omaha, NE"),
            },
        )
        calls = []

        def request(parameters):
            calls.append(parameters)
            return completed_response(payload)

        result = extract_fields("BOL", request, document_text=document_text)

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["fields"]["bol_number"]["value"], "RBL-20773")
        self.assertEqual(result["fields"]["bol_number"]["confidence"], 1.0)
        self.assertEqual(result["metadata"]["context"], "text")

    def test_extract_fields_requires_exactly_one_context(self):
        with self.assertRaises(ValueError):
            extract_fields("BOL", lambda parameters: None)
        with self.assertRaises(ValueError):
            extract_fields("BOL", lambda parameters: None, document_text="x", images=[])

    def test_invalid_evidence_is_an_extraction_failure_after_one_retry(self):
        payload = make_payload(
            "BOL",
            present={"bol_number": ("RBL-20773", "not in the source")},
        )
        calls = []

        def request(parameters):
            calls.append(parameters)
            return completed_response(payload)

        with self.assertRaises(ExtractionFailure) as raised:
            extract_fields("BOL", request, document_text="RBL-20773 only, no other text")
        self.assertEqual(len(calls), 2)
        self.assertEqual(raised.exception.category, "invalid_structured_output")

    def test_technical_failure_is_an_extraction_failure_after_one_retry(self):
        calls = []

        def request(parameters):
            calls.append(parameters)
            raise RetryableRequestFailure("technical_failure")

        with self.assertRaises(ExtractionFailure) as raised:
            extract_fields("BOL", request, document_text="anything")
        self.assertEqual(len(calls), 2)
        self.assertEqual(raised.exception.category, "technical_failure")

    def test_non_retryable_failure_stops_after_one_call(self):
        calls = []

        def request(parameters):
            calls.append(parameters)
            raise NonRetryableRequestFailure("configuration_failure")

        with self.assertRaises(ExtractionFailure):
            extract_fields("BOL", request, document_text="anything")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
