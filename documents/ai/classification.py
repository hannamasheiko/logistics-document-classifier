"""Primary text and visual-fallback classification: OpenAI calls and strict
response validation.

Reuses the routing contract frozen at Task 2E/GE and reviewed in
docs/experiments/primary-confidence.md (text) and Task 5/G2 reviewed in
docs/experiments/scanned-fallback.md (visual): model, prompt/schema version,
and evidence rules are not re-derived here.
"""

import json
import re
import time
from base64 import b64encode
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from PIL import Image


PROVIDER_ID = "openai"
ENDPOINT_ID = "responses"
MODEL = "gpt-5.4-mini-2026-03-17"
CONFIG_ID = "primary-text-evaluation-v2"
PROMPT_ID = "primary-classification-evidence-v2"
SCHEMA_ID = "primary-classification-evidence-v2"
MAX_OUTPUT_TOKENS = 2_000  # raised from 1,200: "medium" reasoning effort uses
# more reasoning tokens (observed 770 on one call) than the "low" effort this
# limit was originally sized for, and reasoning tokens count against this
# budget too.
MAX_RETRIES_PER_DOCUMENT = 1
REQUEST_TIMEOUT_SECONDS = 60.0

FEATURE_IDS = (
    "bol_identity",
    "bol_transport_obligation",
    "bol_shipment_structure",
    "pod_identity",
    "completed_delivery_event",
    "recipient_acknowledgement",
    "transport_invoice_identity",
    "transport_charge_breakdown",
    "payment_obligation",
    "non_target_identity",
    "non_target_primary_purpose",
)

DIAGNOSTIC_IDS = (
    "combined_bol_pod",
    "multiple_target_purposes",
    "insufficient_readable_content",
    "contradictory_evidence",
)


def _observation_schema(description: str) -> dict:
    return {
        "type": "object",
        "description": description,
        "properties": {
            "status": {
                "type": "string",
                "enum": ["present", "absent", "unclear"],
            },
            "evidence": {
                "type": ["string", "null"],
                "description": (
                    "A short exact quote from the document when status is present; "
                    "null when status is absent or unclear."
                ),
            },
        },
        "required": ["status", "evidence"],
        "additionalProperties": False,
    }


FEATURE_DESCRIPTIONS = {
    "bol_identity": "The document explicitly identifies itself as a bill of lading.",
    "bol_transport_obligation": (
        "The document records goods tendered or received by a carrier for transport "
        "and delivery to a consignee, or an equivalent shipment contract function."
    ),
    "bol_shipment_structure": (
        "Operational details jointly identify a transport movement: carrier plus "
        "shipper/consignee or origin/destination plus cargo/packages/weight."
    ),
    "pod_identity": (
        "The document explicitly identifies itself as proof of delivery, a delivery "
        "receipt, or a statement of final delivery status."
    ),
    "completed_delivery_event": (
        "The document records completed delivery with actual delivered status and a "
        "concrete date/time or location."
    ),
    "recipient_acknowledgement": (
        "The document records a recipient/signatory name, signature, or equivalent "
        "completed acknowledgement."
    ),
    "transport_invoice_identity": (
        "The document is an invoice primarily billing for transport or logistics "
        "services by a carrier, broker, or logistics provider."
    ),
    "transport_charge_breakdown": (
        "The document itemizes transport-service charges such as linehaul, freight, "
        "fuel surcharge, detention, chassis, lumper, or similar services."
    ),
    "payment_obligation": (
        "The document establishes a payer/bill-to relationship and an amount due, due "
        "date, or payment terms."
    ),
    "non_target_identity": (
        "The document explicitly identifies any non-target document type outside BOL, "
        "POD, and transport/logistics-service invoice; examples include commercial or "
        "customs invoice, packing list, purchase order, and customs declaration."
    ),
    "non_target_primary_purpose": (
        "Positive content establishes another primary purpose, such as valuing traded "
        "goods through products, quantities, HS codes, origin/destination countries, "
        "Incoterms, or customs totals."
    ),
}

DIAGNOSTIC_DESCRIPTIONS = {
    "combined_bol_pod": (
        "A BOL transport function and an actually completed delivery acknowledgement "
        "are both substantive parts of the same document."
    ),
    "multiple_target_purposes": (
        "Evidence materially supports more than one target class without a clear "
        "primary document purpose."
    ),
    "insufficient_readable_content": (
        "The supplied text is too incomplete or damaged for reliable feature judgments."
    ),
    "contradictory_evidence": (
        "The candidate class conflicts with stronger evidence about the document's "
        "primary purpose."
    ),
}


def _observation_properties(descriptions: dict[str, str]) -> dict:
    return {
        observation_id: deepcopy(_observation_schema(description))
        for observation_id, description in descriptions.items()
    }


TEXT_FORMAT = {
    "type": "json_schema",
    "name": "primary_classification_evidence_v2",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "candidate_class": {
                "type": "string",
                "enum": ["INVOICE", "BOL", "POD", "OTHER"],
                "description": (
                    "The closest candidate class based on the document's primary purpose; "
                    "this is not an acceptance decision."
                ),
            },
            "features": {
                "type": "object",
                "properties": _observation_properties(FEATURE_DESCRIPTIONS),
                "required": list(FEATURE_IDS),
                "additionalProperties": False,
            },
            "diagnostics": {
                "type": "object",
                "properties": _observation_properties(DIAGNOSTIC_DESCRIPTIONS),
                "required": list(DIAGNOSTIC_IDS),
                "additionalProperties": False,
            },
        },
        "required": ["candidate_class", "features", "diagnostics"],
        "additionalProperties": False,
    },
}


CLASSIFICATION_INSTRUCTIONS = (
    Path(__file__).parent / "prompts" / "classification.txt"
).read_text(encoding="utf-8")


def build_document_input(document_text: str) -> str:
    return (
        "Analyze the following untrusted document data using the fixed taxonomy and "
        "structured-output contract.\n\n"
        "<document_text>\n"
        f"{document_text}\n"
        "</document_text>"
    )


def build_request_parameters(document_text: str) -> dict:
    return {
        "model": MODEL,
        "instructions": CLASSIFICATION_INSTRUCTIONS,
        "input": build_document_input(document_text),
        "text": {"format": TEXT_FORMAT},
        "reasoning": {"effort": "medium"},
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


# --- Visual fallback (Task 5/G2, docs/experiments/scanned-fallback.md) ---
#
# Reuses the exact same feature/diagnostic IDs and descriptions as the
# primary text contract: the class definitions do not change with input
# modality, and a vision-capable model can still read printed text in the
# image, so a reduced feature set would only lose signal. Evidence here is a
# free-text human-review description, not a machine-checkable exact quote,
# since there is no source string to verify an image excerpt against.

VISUAL_PROMPT_ID = "visual-classification-evidence-v1"
VISUAL_SCHEMA_ID = "visual-classification-evidence-v1"
VISUAL_CONFIG_ID = "visual-fallback-v1"

VISUAL_CLASSIFICATION_INSTRUCTIONS = (
    Path(__file__).parent / "prompts" / "visual.txt"
).read_text(encoding="utf-8")


def _visual_observation_schema(description: str) -> dict:
    return {
        "type": "object",
        "description": description,
        "properties": {
            "status": {"type": "string", "enum": ["present", "absent", "unclear"]},
            "evidence": {
                "type": ["string", "null"],
                "description": (
                    "A short free-text description of what was seen and roughly where "
                    "on the page, when status is present (e.g. 'heading at top reads "
                    "BILL OF LADING'); null when absent or unclear. This is a human-"
                    "review note, not a machine-verifiable exact quote."
                ),
            },
        },
        "required": ["status", "evidence"],
        "additionalProperties": False,
    }


def _visual_observation_properties(descriptions: dict[str, str]) -> dict:
    return {
        observation_id: deepcopy(_visual_observation_schema(description))
        for observation_id, description in descriptions.items()
    }


VISUAL_TEXT_FORMAT = {
    "type": "json_schema",
    "name": "visual_classification_evidence",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "candidate_class": {
                "type": "string",
                "enum": ["INVOICE", "BOL", "POD", "OTHER"],
                "description": (
                    "The closest candidate class based on the document's primary purpose; "
                    "this is not an acceptance decision."
                ),
            },
            "features": {
                "type": "object",
                "properties": _visual_observation_properties(FEATURE_DESCRIPTIONS),
                "required": list(FEATURE_IDS),
                "additionalProperties": False,
            },
            "diagnostics": {
                "type": "object",
                "properties": _visual_observation_properties(DIAGNOSTIC_DESCRIPTIONS),
                "required": list(DIAGNOSTIC_IDS),
                "additionalProperties": False,
            },
        },
        "required": ["candidate_class", "features", "diagnostics"],
        "additionalProperties": False,
    },
}


def _image_to_base64_png(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return b64encode(buffer.getvalue()).decode("ascii")


def build_visual_request_parameters(images: list[Image.Image]) -> dict:
    content = [
        {
            "type": "input_text",
            "text": (
                "Analyze the attached untrusted page images using the fixed taxonomy "
                "and structured-output contract. The images are the pages of one "
                "document, in reading order."
            ),
        }
    ]
    for image in images:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{_image_to_base64_png(image)}",
                "detail": "high",
            }
        )
    return {
        "model": MODEL,
        "instructions": VISUAL_CLASSIFICATION_INSTRUCTIONS,
        "input": [{"role": "user", "content": content}],
        "text": {"format": VISUAL_TEXT_FORMAT},
        "reasoning": {"effort": "medium"},
        "store": False,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


class StructuredOutputValidationError(ValueError):
    """Common base for structural/evidence validation errors across text,
    visual, and (documents.ai.extraction) field-extraction output, so
    run_structured_call can catch one shared retry boundary regardless of
    which contract produced the response."""


class VisualOutputValidationError(StructuredOutputValidationError):
    def __init__(self, code: str, observation_id: str | None = None):
        messages = {
            "unexpected_root_fields": "Model output has unexpected root fields.",
            "invalid_candidate_class": "Model output has an invalid candidate class.",
            "unexpected_observation_fields": "Model output has unexpected observation fields.",
            "unexpected_observation_shape": "Observation has unexpected fields.",
            "invalid_status": "Observation has an invalid status.",
            "missing_present_evidence": "Present observation requires a description.",
            "non_null_inactive_evidence": "Evidence must be null for absent or unclear.",
        }
        super().__init__(messages[code])
        self.code = code
        self.observation_id = observation_id


def validate_visual_output(payload: dict) -> None:
    expected_root = {"candidate_class", "features", "diagnostics"}
    if set(payload) != expected_root:
        raise VisualOutputValidationError("unexpected_root_fields")
    if payload["candidate_class"] not in {"INVOICE", "BOL", "POD", "OTHER"}:
        raise VisualOutputValidationError("invalid_candidate_class")

    groups = (
        (payload["features"], FEATURE_IDS),
        (payload["diagnostics"], DIAGNOSTIC_IDS),
    )
    for observations, expected_ids in groups:
        if set(observations) != set(expected_ids):
            raise VisualOutputValidationError("unexpected_observation_fields")
        for observation_id, observation in observations.items():
            if set(observation) != {"status", "evidence"}:
                raise VisualOutputValidationError("unexpected_observation_shape", observation_id)
            status = observation["status"]
            evidence = observation["evidence"]
            if status not in {"present", "absent", "unclear"}:
                raise VisualOutputValidationError("invalid_status", observation_id)
            if status == "present":
                if not isinstance(evidence, str) or not evidence.strip():
                    raise VisualOutputValidationError("missing_present_evidence", observation_id)
            elif evidence is not None:
                raise VisualOutputValidationError("non_null_inactive_evidence", observation_id)


class ModelOutputValidationError(StructuredOutputValidationError):
    def __init__(self, code: str, observation_id: str | None = None):
        messages = {
            "unexpected_root_fields": "Model output has unexpected root fields.",
            "invalid_candidate_class": "Model output has an invalid candidate class.",
            "unexpected_observation_fields": "Model output has unexpected observation fields.",
            "unexpected_observation_shape": "Observation has unexpected fields.",
            "invalid_status": "Observation has an invalid status.",
            "missing_present_evidence": "Present observation requires evidence.",
            "evidence_not_exact_substring": "Evidence is not an exact substring.",
            "non_null_inactive_evidence": "Evidence must be null for absent or unclear.",
        }
        super().__init__(messages[code])
        self.code = code
        self.observation_id = observation_id


def evidence_matches_source(evidence: str, document_text: str) -> bool:
    if evidence in document_text:
        return True
    normalized_evidence = re.sub(r"\s+", " ", evidence).strip()
    normalized_document = re.sub(r"\s+", " ", document_text).strip()
    return normalized_evidence in normalized_document


def normalize_evidence_quotes(payload: dict, document_text: str) -> dict:
    normalized = deepcopy(payload)
    for group_name in ("features", "diagnostics"):
        observations = normalized.get(group_name)
        if not isinstance(observations, dict):
            continue
        for observation in observations.values():
            if not isinstance(observation, dict):
                continue
            evidence = observation.get("evidence")
            if (
                isinstance(evidence, str)
                and len(evidence) >= 2
                and evidence[0] == evidence[-1] == '"'
                and not evidence_matches_source(evidence, document_text)
                and evidence_matches_source(evidence[1:-1], document_text)
            ):
                observation["evidence"] = evidence[1:-1]
    return normalized


def validate_model_output(payload: dict, document_text: str) -> None:
    expected_root = {"candidate_class", "features", "diagnostics"}
    if set(payload) != expected_root:
        raise ModelOutputValidationError("unexpected_root_fields")
    if payload["candidate_class"] not in {"INVOICE", "BOL", "POD", "OTHER"}:
        raise ModelOutputValidationError("invalid_candidate_class")

    groups = (
        (payload["features"], FEATURE_IDS),
        (payload["diagnostics"], DIAGNOSTIC_IDS),
    )
    for observations, expected_ids in groups:
        if set(observations) != set(expected_ids):
            raise ModelOutputValidationError("unexpected_observation_fields")
        for observation_id, observation in observations.items():
            if set(observation) != {"status", "evidence"}:
                raise ModelOutputValidationError(
                    "unexpected_observation_shape",
                    observation_id,
                )

            status = observation["status"]
            evidence = observation["evidence"]
            if status not in {"present", "absent", "unclear"}:
                raise ModelOutputValidationError("invalid_status", observation_id)
            if status == "present":
                if not isinstance(evidence, str) or not evidence.strip():
                    raise ModelOutputValidationError(
                        "missing_present_evidence",
                        observation_id,
                    )
                if not evidence_matches_source(evidence, document_text):
                    raise ModelOutputValidationError(
                        "evidence_not_exact_substring",
                        observation_id,
                    )
            elif evidence is not None:
                raise ModelOutputValidationError(
                    "non_null_inactive_evidence",
                    observation_id,
                )


class RetryableRequestFailure(Exception):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


class NonRetryableRequestFailure(Exception):
    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


class ClassificationFailure(Exception):
    """Raised when classification could not produce a usable result.

    This is a technical failure, never a semantic OTHER/UNCERTAIN outcome.
    """

    def __init__(self, category: str, attempts: list[dict]):
        super().__init__(category)
        self.category = category
        self.attempts = attempts


def classify_client_exception(error: Exception) -> tuple[bool, str]:
    retryable_names = {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
    }
    configuration_names = {
        "AuthenticationError",
        "BadRequestError",
        "NotFoundError",
        "PermissionDeniedError",
        "UnprocessableEntityError",
    }
    error_name = type(error).__name__
    if error_name in retryable_names:
        return True, "technical_failure"
    if error_name in configuration_names:
        return False, "configuration_failure"
    return False, "unexpected_client_failure"


def create_openai_client():
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError(
            "The OpenAI SDK is not installed in this Python environment."
        ) from error
    return OpenAI(max_retries=0, timeout=REQUEST_TIMEOUT_SECONDS)


def _contains_refusal(value) -> bool:
    if isinstance(value, dict):
        if value.get("type") == "refusal":
            return True
        return any(_contains_refusal(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_refusal(item) for item in value)
    return False


def normalize_sdk_response(response, latency_seconds: float) -> dict:
    response_data = response.model_dump()
    status = "refused" if _contains_refusal(response_data.get("output")) else response.status
    incomplete_details = getattr(response, "incomplete_details", None)
    output_details = getattr(response.usage, "output_tokens_details", None)

    return {
        "response_id": response.id,
        "status": status,
        "incomplete_reason": getattr(incomplete_details, "reason", None),
        "output_text": response.output_text or "",
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "reasoning_tokens": getattr(output_details, "reasoning_tokens", 0) or 0,
        },
        "latency_seconds": round(latency_seconds, 3),
    }


def request_openai(client, parameters: dict) -> dict:
    started_at = time.monotonic()
    try:
        response = client.responses.create(**parameters)
    except Exception as error:
        retryable, category = classify_client_exception(error)
        if retryable:
            raise RetryableRequestFailure(category) from None
        raise NonRetryableRequestFailure(category) from None
    return normalize_sdk_response(response, time.monotonic() - started_at)


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


def run_structured_call(parameters: dict, request, validate_and_normalize) -> dict:
    """Shared retry/error-handling loop for one structured classification call.

    `validate_and_normalize(payload) -> normalized_payload` raises a
    StructuredOutputValidationError subclass (exposing `.code` and an
    optional per-field identifier attribute) for an invalid payload; shared
    by classification's own subclasses and documents.ai.extraction's.
    Returns
    {"observations": normalized_payload, "attempts": [...]} on success.
    Raises ClassificationFailure after exhausting the one-retry policy.
    """
    attempts_metadata: list[dict] = []

    for attempt in range(1, MAX_RETRIES_PER_DOCUMENT + 2):
        can_retry = attempt <= MAX_RETRIES_PER_DOCUMENT

        try:
            response = request(parameters)
        except (RetryableRequestFailure, NonRetryableRequestFailure) as error:
            attempts_metadata.append({"attempt": attempt, "error_category": error.category})
            if isinstance(error, RetryableRequestFailure) and can_retry:
                continue
            raise ClassificationFailure(error.category, attempts_metadata) from None

        attempt_metadata = _attempt_metadata(attempt, response)

        if response.get("status") == "incomplete":
            reason = response.get("incomplete_reason")
            category = (
                "output_limit_incomplete"
                if reason == "max_output_tokens"
                else "incomplete_response"
            )
            attempt_metadata["error_category"] = category
            attempts_metadata.append(attempt_metadata)
            if category != "output_limit_incomplete" and can_retry:
                continue
            raise ClassificationFailure(category, attempts_metadata)

        if response.get("status") == "refused":
            attempt_metadata["error_category"] = "refusal"
            attempts_metadata.append(attempt_metadata)
            if can_retry:
                continue
            raise ClassificationFailure("refusal", attempts_metadata)

        try:
            payload = json.loads(response.get("output_text", ""))
        except json.JSONDecodeError:
            attempt_metadata["error_category"] = "invalid_structured_output"
            attempt_metadata["validation_error_code"] = "invalid_json"
            attempts_metadata.append(attempt_metadata)
            if can_retry:
                continue
            raise ClassificationFailure("invalid_structured_output", attempts_metadata)

        try:
            normalized_payload = validate_and_normalize(payload)
        except StructuredOutputValidationError as error:
            attempt_metadata["error_category"] = "invalid_structured_output"
            attempt_metadata["validation_error_code"] = error.code
            if error.observation_id is not None:
                attempt_metadata["observation_id"] = error.observation_id
            attempts_metadata.append(attempt_metadata)
            if can_retry:
                continue
            raise ClassificationFailure("invalid_structured_output", attempts_metadata)

        attempts_metadata.append(attempt_metadata)
        return {"observations": normalized_payload, "attempts": attempts_metadata}

    raise AssertionError("classification call must return or raise within its retry loop")


def classify_document_text(document_text: str, request) -> dict:
    """Classify one document's already-extracted text.

    `request` is an injected `parameters -> response dict` boundary (see
    `request_openai`), so tests can fake the OpenAI call without a real SDK
    client. Returns {"observations": <validated payload>, "metadata": {...}}
    on success. Raises ClassificationFailure for any technical or invalid-
    output outcome, after at most one retry, per the GE-approved policy.
    Never returns or raises a semantic OTHER/UNCERTAIN result: that decision
    belongs to documents.services.routing.
    """

    def validate_and_normalize(payload: dict) -> dict:
        normalized = normalize_evidence_quotes(payload, document_text)
        validate_model_output(normalized, document_text)
        return normalized

    result = run_structured_call(
        build_request_parameters(document_text), request, validate_and_normalize
    )
    return {
        "observations": result["observations"],
        "metadata": {
            "provider": PROVIDER_ID,
            "endpoint": ENDPOINT_ID,
            "model": MODEL,
            "config_id": CONFIG_ID,
            "prompt_id": PROMPT_ID,
            "schema_id": SCHEMA_ID,
            "attempts": result["attempts"],
        },
    }


def classify_document_images(images: list[Image.Image], request) -> dict:
    """Visual fallback: classify one document from rendered page images.

    Same injected `request` boundary and one-retry technical-failure policy
    as `classify_document_text` (Task 5/G2 agreed bounds). Evidence is not
    exact-quote validated (see `validate_visual_output`): there is no source
    string to check an image excerpt against.
    """

    def validate_and_normalize(payload: dict) -> dict:
        validate_visual_output(payload)
        return payload

    result = run_structured_call(
        build_visual_request_parameters(images), request, validate_and_normalize
    )
    return {
        "observations": result["observations"],
        "metadata": {
            "provider": PROVIDER_ID,
            "endpoint": ENDPOINT_ID,
            "model": MODEL,
            "config_id": VISUAL_CONFIG_ID,
            "prompt_id": VISUAL_PROMPT_ID,
            "schema_id": VISUAL_SCHEMA_ID,
            "attempts": result["attempts"],
        },
    }
