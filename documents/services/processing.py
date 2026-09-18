"""Synchronous attempt lifecycle: text extraction, primary classification,
routing, (Task 6) one visual fallback escalation, and (Task 8) planned field
extraction for an accepted result.

DB writes happen only before and after each external OpenAI call, never
around it. At most one visual fallback call per attempt: fallback routing
may only ACCEPT or end as UNCERTAIN, it never escalates further. Field
extraction (Task 7/G3) only ever runs for an ACCEPTED result and never
changes that result if it fails.
"""

from documents.ai import classification, extraction
from documents.ai.classification import ClassificationFailure
from documents.ai.extraction import ExtractionFailure
from documents.models import ProcessingAttempt
from documents.services import routing
from documents.services.pdf import extract_text, render_all_pages


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

    request = request or build_default_request()

    if not document_text.strip():
        # Neither native text nor OCR found anything anywhere in the
        # document: there is nothing to feed the text classifier. Still try
        # the visual fallback once before giving up, since it reads pixels
        # directly and does not depend on OCR having found any text (Task
        # 5/G2 showed it can succeed exactly where OCR text was unusable).
        attempt.primary_metadata = {"skipped": True, "reason": "no_extractable_text"}
        return _run_visual_fallback(attempt, request)

    try:
        primary_outcome = classification.classify_document_text(document_text, request)
    except ClassificationFailure as failure:
        _mark_failed(
            attempt,
            stage="classification",
            category=failure.category,
            reason=f"Primary classification failed: {failure.category}.",
            primary_metadata={"attempts": failure.attempts},
        )
        return attempt

    primary_routing = routing.evaluate_routing(primary_outcome["observations"])
    attempt.primary_observations = primary_outcome["observations"]
    attempt.primary_metadata = {**primary_outcome["metadata"], "routing": primary_routing}

    if primary_routing["action"] == "ACCEPT":
        _accept(attempt, primary_routing, request, document_text=document_text)
        return attempt

    if primary_routing["action"] == "UNCERTAIN_NO_FALLBACK":
        # Established ambiguity never escalates, even once fallback exists.
        _uncertain(attempt, primary_routing)
        return attempt

    # action == "ESCALATE": one visual fallback attempt, on the same original PDF.
    return _run_visual_fallback(attempt, request)


def _run_visual_fallback(attempt: ProcessingAttempt, request) -> ProcessingAttempt:
    try:
        with attempt.original_file.open("rb") as pdf_file:
            pdf_bytes = pdf_file.read()
        images = render_all_pages(pdf_bytes)
    except Exception:
        _mark_failed(
            attempt,
            stage="visual_fallback",
            category="render_error",
            reason="Could not render the original PDF for the visual fallback.",
        )
        return attempt

    try:
        fallback_outcome = classification.classify_document_images(images, request)
    except ClassificationFailure as failure:
        _mark_failed(
            attempt,
            stage="visual_fallback",
            category=failure.category,
            reason=f"Visual fallback failed: {failure.category}.",
            fallback_metadata={"attempts": failure.attempts},
        )
        return attempt

    fallback_routing = routing.evaluate_routing(fallback_outcome["observations"])
    attempt.fallback_observations = fallback_outcome["observations"]
    attempt.fallback_metadata = {**fallback_outcome["metadata"], "routing": fallback_routing}

    if fallback_routing["action"] == "ACCEPT":
        _accept(attempt, fallback_routing, request, images=images)
    else:
        # ESCALATE or UNCERTAIN_NO_FALLBACK from the fallback both end as
        # UNCERTAIN: fallback routing may only accept or end uncertain, it
        # never triggers a second escalation ("one fallback per attempt").
        _uncertain(attempt, fallback_routing)

    return attempt


def _accept(
    attempt: ProcessingAttempt,
    routing_result: dict,
    request,
    *,
    document_text: str | None = None,
    images=None,
) -> None:
    attempt.status = ProcessingAttempt.Status.ACCEPTED
    attempt.accepted_label = routing_result["candidate_class"]
    attempt.routing_score = routing_result["routing_score"]
    attempt.score_method = routing_result["score_method"]
    _run_extraction(
        attempt,
        routing_result["candidate_class"],
        request,
        document_text=document_text,
        images=images,
    )
    attempt.save()


def _run_extraction(
    attempt: ProcessingAttempt,
    class_name: str,
    request,
    *,
    document_text: str | None,
    images,
) -> None:
    """Extraction reuses whichever context already produced the ACCEPTED
    result (Task 7/G3 execution rule). A failure here is recorded on the
    attempt's own extraction_* fields and never touches the classification
    status/label already set by the caller. OTHER has no extraction schema
    (G3): extraction_status stays at its NOT_APPLICABLE default."""
    if class_name == "OTHER":
        return

    try:
        outcome = extraction.extract_fields(
            class_name, request, document_text=document_text, images=images
        )
    except ExtractionFailure as failure:
        attempt.extraction_status = ProcessingAttempt.ExtractionStatus.UNAVAILABLE
        attempt.extraction_failure_category = failure.category
        attempt.extraction_failure_reason = f"Field extraction failed: {failure.category}."
        attempt.extraction_metadata = {"attempts": failure.attempts}
        return

    attempt.extraction_status = ProcessingAttempt.ExtractionStatus.COMPLETED
    attempt.extraction_result = outcome["fields"]
    attempt.extraction_metadata = outcome["metadata"]


def _uncertain(attempt: ProcessingAttempt, routing_result: dict) -> None:
    attempt.status = ProcessingAttempt.Status.UNCERTAIN
    attempt.accepted_label = None
    attempt.routing_score = routing_result["routing_score"]
    attempt.score_method = routing_result["score_method"]
    attempt.save()


def _mark_failed(
    attempt: ProcessingAttempt,
    *,
    stage: str,
    category: str,
    reason: str,
    primary_metadata: dict | None = None,
    fallback_metadata: dict | None = None,
) -> None:
    attempt.status = ProcessingAttempt.Status.FAILED
    attempt.failure_stage = stage
    attempt.failure_category = category
    attempt.failure_reason = reason
    if primary_metadata is not None:
        attempt.primary_metadata = primary_metadata
    if fallback_metadata is not None:
        attempt.fallback_metadata = fallback_metadata
    attempt.save()
