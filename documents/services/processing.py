"""Synchronous attempt lifecycle: text extraction, primary classification, routing.

Iteration 1 has no visual fallback and no OCR: an unresolved primary result
ends as semantic UNCERTAIN. DB writes happen only before and after the
external OpenAI call, never around it.
"""

from documents.ai import classification
from documents.ai.classification import ClassificationFailure
from documents.models import ProcessingAttempt
from documents.services import routing
from documents.services.pdf import extract_text


def build_default_request():
    client = classification.create_openai_client()
    return lambda parameters: classification.request_openai(client, parameters)


def run_classification(attempt: ProcessingAttempt, request=None) -> ProcessingAttempt:
    try:
        with attempt.original_file.open("rb") as pdf_file:
            document_text = extract_text(pdf_file)
    except Exception as error:
        _mark_failed(
            attempt,
            stage="text_extraction",
            category="parser_error",
            reason="The stored PDF could not be read for text extraction.",
        )
        return attempt

    if not document_text.strip():
        _mark_failed(
            attempt,
            stage="text_extraction",
            category="no_extractable_text",
            reason="The PDF has no extractable text layer.",
        )
        return attempt

    request = request or build_default_request()

    try:
        outcome = classification.classify_document_text(document_text, request)
    except ClassificationFailure as failure:
        _mark_failed(
            attempt,
            stage="classification",
            category=failure.category,
            reason=f"Primary classification failed: {failure.category}.",
            metadata={"attempts": failure.attempts},
        )
        return attempt

    routing_result = routing.evaluate_routing(outcome["observations"])

    attempt.primary_observations = outcome["observations"]
    attempt.primary_metadata = {**outcome["metadata"], "routing": routing_result}
    attempt.routing_score = routing_result["routing_score"]
    attempt.score_method = routing_result["score_method"]

    if routing_result["action"] == "ACCEPT":
        attempt.status = ProcessingAttempt.Status.ACCEPTED
        attempt.accepted_label = routing_result["candidate_class"]
    else:
        # ESCALATE and UNCERTAIN_NO_FALLBACK both end as semantic UNCERTAIN in
        # Iteration 1; the routing reason distinguishes them in primary_metadata.
        attempt.status = ProcessingAttempt.Status.UNCERTAIN
        attempt.accepted_label = None

    attempt.save()
    return attempt


def _mark_failed(
    attempt: ProcessingAttempt,
    *,
    stage: str,
    category: str,
    reason: str,
    metadata: dict | None = None,
) -> None:
    attempt.status = ProcessingAttempt.Status.FAILED
    attempt.failure_stage = stage
    attempt.failure_category = category
    attempt.failure_reason = reason
    if metadata is not None:
        attempt.primary_metadata = metadata
    attempt.save()
