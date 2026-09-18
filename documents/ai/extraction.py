"""Planned field extraction: OpenAI calls, validation, and the deterministic
field-confidence layer agreed at Task 7/G3
(docs/decisions/field-extraction-contract.md).

Only ever called for an already-ACCEPTED attempt. Reuses the same OpenAI
call/retry machinery as documents.ai.classification (same one-retry
technical-failure policy, same timeout, same client), and the same
evidence-provenance rule for text/OCR context: an exact, continuous quote.
Visual-fallback context uses free-text evidence, exactly like visual
classification, since there is no source string to check an image excerpt
against.
"""

import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PIL import Image

from documents.ai.classification import (
    MAX_OUTPUT_TOKENS,
    MODEL,
    PROVIDER_ID,
    ENDPOINT_ID,
    ClassificationFailure,
    StructuredOutputValidationError,
    evidence_matches_source,
    run_structured_call,
)
from documents.ai.classification import (
    _image_to_base64_png as image_to_base64_png,
)


CONFIG_ID = "field-extraction-v1"
PROMPT_ID = "field-extraction-v1"
SCHEMA_ID = "field-extraction-v1"

EXTRACTION_INSTRUCTIONS = (
    Path(__file__).parent / "prompts" / "extraction.txt"
).read_text(encoding="utf-8")


# --- Class-specific field schema (Task 7/G3) ---
#
# `destination` on BOL and POD is not a new "just in case" field: it is
# already part of the frozen classification feature `bol_shipment_structure`
# ("carrier plus shipper/consignee or origin/destination plus
# cargo/packages/weight"), so extracting it explicitly costs little and
# avoids redoing this later for an already-recognized core fact.
FIELD_DEFINITIONS = {
    "BOL": {
        "bol_number": ("identifier", "The bill of lading's own reference/tracking number, however labeled."),
        "carrier": ("string", "The transporting carrier's name."),
        "shipper": ("string", "The shipper/origin party's name (and location, if given together)."),
        "consignee": ("string", "The consignee/receiving party's name (and location, if given together)."),
        "ship_date": ("date", "The date the shipment was tendered/shipped, if an actual calendar date is printed."),
        "destination": ("string", "The shipment's destination location."),
    },
    "POD": {
        "tracking_number": ("identifier", "The document's own reference/tracking identifier, however labeled (e.g. certificate, receipt, or waybill number)."),
        "carrier": ("string", "The delivering carrier's name."),
        "recipient_name": ("string", "The name of the person who received/signed for the delivery."),
        "delivery_date": ("date", "The date (and time, if given) the delivery was completed."),
        "destination": ("string", "The delivery location."),
    },
    "INVOICE": {
        "invoice_number": ("identifier", "The invoice's own reference number."),
        "provider": ("string", "The carrier/broker/logistics provider issuing the invoice."),
        "bill_to": ("string", "The payer/billed party's name."),
        "amount_due": ("amount", "The total amount due, as printed."),
        "due_date": ("date", "The actual calendar due date, if one is printed. Payment terms alone (e.g. 'Net 21') are not a date."),
    },
}

# Two-field pairs where an identical value on both sides is suspicious
# (defined only where the schema has a natural pair of distinct-party
# fields; POD has no equivalent pair, so none is defined for it).
CONSISTENCY_PAIRS = {
    "BOL": [("shipper", "consignee")],
    "INVOICE": [("provider", "bill_to")],
    "POD": [],
}

MAX_IDENTIFIER_LENGTH = 40

_DATE_PATTERNS = (
    (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),
    (r"\d{1,2}/\d{1,2}/\d{4}", "%m/%d/%Y"),
    (
        r"(January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+\d{1,2},\s*\d{4}",
        "%B %d, %Y",
    ),
)


class ExtractionOutputValidationError(StructuredOutputValidationError):
    """`observation_id` holds the field name, named to match the shared
    StructuredOutputValidationError interface used by run_structured_call."""

    def __init__(self, code: str, observation_id: str | None = None):
        messages = {
            "unexpected_root_fields": "Extraction output has unexpected root fields.",
            "unexpected_field_shape": "Field result has unexpected fields.",
            "invalid_status": "Field result has an invalid status.",
            "missing_present_value": "Present field requires a value.",
            "missing_present_evidence": "Present field requires evidence.",
            "evidence_not_exact_substring": "Evidence is not an exact substring.",
            "value_not_in_evidence": "Field value is not supported by its evidence.",
            "non_null_inactive_value_or_evidence": "Value/evidence must be null unless present.",
        }
        super().__init__(messages[code])
        self.code = code
        self.observation_id = observation_id


class ExtractionFailure(Exception):
    """Raised when extraction could not produce a usable result.

    Always a technical failure; extraction never itself decides the document
    is a different class or invents a semantic outcome. Per the G3 contract,
    this must never change an attempt's already-ACCEPTED classification.
    """

    def __init__(self, category: str, attempts: list[dict]):
        super().__init__(category)
        self.category = category
        self.attempts = attempts


def _field_result_schema(description: str) -> dict:
    return {
        "type": "object",
        "description": description,
        "properties": {
            "status": {"type": "string", "enum": ["present", "missing", "unclear"]},
            "value": {
                "type": ["string", "null"],
                "description": "The value exactly as printed/shown when status is present; null otherwise.",
            },
            "evidence": {
                "type": ["string", "null"],
                "description": (
                    "An exact continuous quote (text/OCR context) or a short free-text "
                    "description of what was seen and where (visual context) when status "
                    "is present; null otherwise."
                ),
            },
        },
        "required": ["status", "value", "evidence"],
        "additionalProperties": False,
    }


def build_extraction_text_format(class_name: str) -> dict:
    fields = FIELD_DEFINITIONS[class_name]
    properties = {
        field_name: deepcopy(_field_result_schema(description))
        for field_name, (_field_type, description) in fields.items()
    }
    return {
        "type": "json_schema",
        "name": f"field_extraction_{class_name.lower()}",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": list(fields),
            "additionalProperties": False,
        },
    }


def build_field_list(class_name: str) -> str:
    fields = FIELD_DEFINITIONS[class_name]
    return "\n".join(
        f"- `{field_name}` ({field_type}): {description}"
        for field_name, (field_type, description) in fields.items()
    )


def build_extraction_text_request_parameters(class_name: str, document_text: str) -> dict:
    input_text = (
        f"Extract the following fields for this {class_name} document:\n"
        f"{build_field_list(class_name)}\n\n"
        "Analyze the untrusted document data below using the fixed schema.\n\n"
        "<document_text>\n"
        f"{document_text}\n"
        "</document_text>"
    )
    return {
        "model": MODEL,
        "instructions": EXTRACTION_INSTRUCTIONS,
        "input": input_text,
        "text": {"format": build_extraction_text_format(class_name)},
        "reasoning": {"effort": "medium"},
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def build_extraction_visual_request_parameters(class_name: str, images: list[Image.Image]) -> dict:
    content = [
        {
            "type": "input_text",
            "text": (
                f"Extract the following fields for this {class_name} document:\n"
                f"{build_field_list(class_name)}\n\n"
                "Analyze the attached untrusted page images using the fixed schema. "
                "The images are the pages of one document, in reading order."
            ),
        }
    ]
    for image in images:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{image_to_base64_png(image)}",
                "detail": "high",
            }
        )
    return {
        "model": MODEL,
        "instructions": EXTRACTION_INSTRUCTIONS,
        "input": [{"role": "user", "content": content}],
        "text": {"format": build_extraction_text_format(class_name)},
        "reasoning": {"effort": "medium"},
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def validate_extraction_output(payload: dict, class_name: str, document_text: str | None) -> None:
    """`document_text` is the text/OCR context to check evidence against, or
    None for visual context, where evidence is not exact-quote checked."""
    expected_fields = set(FIELD_DEFINITIONS[class_name])
    if set(payload) != expected_fields:
        raise ExtractionOutputValidationError("unexpected_root_fields")

    for field_name, field_result in payload.items():
        if set(field_result) != {"status", "value", "evidence"}:
            raise ExtractionOutputValidationError("unexpected_field_shape", field_name)

        status = field_result["status"]
        value = field_result["value"]
        evidence = field_result["evidence"]
        if status not in {"present", "missing", "unclear"}:
            raise ExtractionOutputValidationError("invalid_status", field_name)

        if status == "present":
            if not isinstance(value, str) or not value.strip():
                raise ExtractionOutputValidationError("missing_present_value", field_name)
            if not isinstance(evidence, str) or not evidence.strip():
                raise ExtractionOutputValidationError("missing_present_evidence", field_name)
            if document_text is not None and not evidence_matches_source(evidence, document_text):
                raise ExtractionOutputValidationError("evidence_not_exact_substring", field_name)
            if document_text is not None:
                normalized_value = re.sub(r"\s+", " ", value).strip()
                normalized_evidence = re.sub(r"\s+", " ", evidence).strip()
                if normalized_value not in normalized_evidence:
                    raise ExtractionOutputValidationError("value_not_in_evidence", field_name)
        elif value is not None or evidence is not None:
            raise ExtractionOutputValidationError("non_null_inactive_value_or_evidence", field_name)


# --- Deterministic validators, contradictions, and field confidence ---


def validate_date(value: str) -> dict:
    for pattern, format_string in _DATE_PATTERNS:
        match = re.search(pattern, value)
        if not match:
            continue
        try:
            from datetime import datetime

            parsed = datetime.strptime(match.group(0), format_string)
        except ValueError:
            continue
        return {"valid": True, "reason": None, "normalized_value": parsed.date().isoformat()}
    return {"valid": False, "reason": "no_parseable_date_found", "normalized_value": None}


def validate_amount(value: str) -> dict:
    match = re.fullmatch(
        r"(?:USD\s*)?\$?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?",
        value.strip(),
    )
    if not match:
        return {"valid": False, "reason": "no_parseable_amount_found", "normalized_value": None}
    try:
        numeric_value = re.sub(r"^(?:USD\s*)?\$?\s*", "", match.group(0))
        amount = Decimal(numeric_value.replace(",", ""))
    except InvalidOperation:
        return {"valid": False, "reason": "no_parseable_amount_found", "normalized_value": None}
    return {"valid": True, "reason": None, "normalized_value": f"{amount:.2f}"}


def validate_identifier(value: str) -> dict:
    if len(value) > MAX_IDENTIFIER_LENGTH:
        return {"valid": False, "reason": "implausibly_long", "normalized_value": None}
    return {"valid": True, "reason": None, "normalized_value": value}


_VALIDATORS_BY_TYPE = {
    "date": validate_date,
    "amount": validate_amount,
    "identifier": validate_identifier,
}


def find_contradictions(fields: dict, class_name: str) -> dict[str, list[str]]:
    contradictions: dict[str, list[str]] = {}
    for field_a, field_b in CONSISTENCY_PAIRS.get(class_name, []):
        result_a = fields[field_a]
        result_b = fields[field_b]
        if (
            result_a["status"] == "present"
            and result_b["status"] == "present"
            and result_a["value"] == result_b["value"]
        ):
            contradictions.setdefault(field_a, []).append(field_b)
            contradictions.setdefault(field_b, []).append(field_a)
    return contradictions


def compute_field_confidence(status: str, validation: dict | None, has_contradiction: bool) -> float | None:
    if status != "present":
        return None
    if has_contradiction:
        return 0.0
    if validation is not None and not validation["valid"]:
        return 0.5
    return 1.0


def enrich_fields(raw_fields: dict, class_name: str) -> dict:
    """Adds validation/confidence/contradiction_with to each validated raw
    field result, per the G3 formula. Never rewrites `value`."""
    contradictions = find_contradictions(raw_fields, class_name)
    enriched = {}
    for field_name, (field_type, _description) in FIELD_DEFINITIONS[class_name].items():
        raw = raw_fields[field_name]
        status = raw["status"]
        validator = _VALIDATORS_BY_TYPE.get(field_type)
        validation = validator(raw["value"]) if status == "present" and validator else None
        contradiction_with = contradictions.get(field_name)
        enriched[field_name] = {
            "value": raw["value"],
            "status": status,
            "evidence": raw["evidence"],
            "validation": validation,
            "confidence": compute_field_confidence(status, validation, bool(contradiction_with)),
            "contradiction_with": contradiction_with,
        }
    return enriched


def _attempt_metadata(attempt: int, response: dict) -> dict:
    usage = response.get("usage", {})
    return {
        "attempt": attempt,
        "response_id": response.get("response_id"),
        "response_status": response.get("status"),
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "reasoning_tokens": usage.get("reasoning_tokens", 0),
        },
        "latency_seconds": response.get("latency_seconds"),
    }


def extract_fields(class_name: str, request, *, document_text: str | None = None, images=None) -> dict:
    """Extract this class's fields from whichever context already produced
    the ACCEPTED result: `document_text` for primary text/OCR, or `images`
    for visual fallback (exactly one of the two must be given). Reuses the
    same one-retry technical-failure policy as classification. Returns
    {"fields": <enriched per-field results>, "metadata": {...}}. Raises
    ExtractionFailure on any technical/invalid-output outcome.
    """
    if (document_text is None) == (images is None):
        raise ValueError("Pass exactly one of document_text or images.")

    if document_text is not None:
        parameters = build_extraction_text_request_parameters(class_name, document_text)
    else:
        parameters = build_extraction_visual_request_parameters(class_name, images)

    def validate_and_normalize(payload: dict) -> dict:
        validate_extraction_output(payload, class_name, document_text)
        return payload

    try:
        result = run_structured_call(parameters, request, validate_and_normalize)
    except ClassificationFailure as failure:
        raise ExtractionFailure(failure.category, failure.attempts) from None

    return {
        "fields": enrich_fields(result["observations"], class_name),
        "metadata": {
            "provider": PROVIDER_ID,
            "endpoint": ENDPOINT_ID,
            "model": MODEL,
            "config_id": CONFIG_ID,
            "prompt_id": PROMPT_ID,
            "schema_id": SCHEMA_ID,
            "context": "text" if document_text is not None else "visual",
            "attempts": result["attempts"],
        },
    }
