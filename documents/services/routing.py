"""Deterministic acceptance/ambiguity/escalation routing for primary and
visual-fallback classification.

Frozen at Task 2E/GE (docs/experiments/primary-confidence.md): critical
feature combinations, rule order, score method, and acceptance threshold are
not re-derived here. Model-reported cross-class diagnostics are advisory only
and never override these backend-derived combinations, with one exception
added at Task 5/G2 (docs/experiments/scanned-fallback.md):
`insufficient_readable_content` is promoted to a deterministic override,
checked before every other rule, because a response that flags its own
input as unreadable cannot be trusted to also report a correct combination.
This was empirically necessary for OCR-sourced text (a garbled-text response
still assembled a spurious complete combination) and applied uniformly here
rather than only for OCR/visual calls, since real native text triggering
this diagnostic would be an equally valid reason to distrust the response.
"""

ROUTING_RULES_ID = "critical-combinations-primary-v1"
SCORE_METHOD_ID = "critical-feature-coverage-v1"
ACCEPTANCE_THRESHOLD = 1.0

CRITICAL_FEATURES = {
    "BOL": (
        "bol_identity",
        "bol_transport_obligation",
        "bol_shipment_structure",
    ),
    "POD": (
        "pod_identity",
        "completed_delivery_event",
        "recipient_acknowledgement",
    ),
    "INVOICE": (
        "transport_invoice_identity",
        "transport_charge_breakdown",
        "payment_obligation",
    ),
    "OTHER": (
        "non_target_identity",
        "non_target_primary_purpose",
    ),
}

TARGET_CLASSES = ("INVOICE", "BOL", "POD")


def _present(observations: dict, feature_id: str) -> bool:
    return observations["features"][feature_id]["status"] == "present"


def _match_ratio(observations: dict, class_name: str) -> float:
    required = CRITICAL_FEATURES[class_name]
    present_count = sum(_present(observations, feature_id) for feature_id in required)
    return present_count / len(required)


def evaluate_routing(observations: dict) -> dict:
    """Apply the frozen primary routing rules to one validated model observation.

    `observations` is the normalized, evidence-validated payload produced by
    `documents.ai.classification.classify_document_text` (never raw/unvalidated
    model output). Returns a routing result with `action` one of `ACCEPT`,
    `ESCALATE`, or `UNCERTAIN_NO_FALLBACK`, plus a `reason` and the nullable
    `candidate_class` that is only meaningful when `action == "ACCEPT"`.
    """
    candidate_class = observations["candidate_class"]

    if observations["diagnostics"]["insufficient_readable_content"]["status"] == "present":
        return {
            "candidate_class": candidate_class,
            "routing_score": None,
            "score_method": SCORE_METHOD_ID,
            "acceptance_threshold": ACCEPTANCE_THRESHOLD,
            "routing_rules_id": ROUTING_RULES_ID,
            "class_match_ratios": None,
            "complete_classes": None,
            "advisory_model_diagnostics": None,
            "action": "ESCALATE",
            "reason": "insufficient_readable_content",
        }

    match_ratios = {
        class_name: _match_ratio(observations, class_name)
        for class_name in CRITICAL_FEATURES
    }
    complete_classes = [
        class_name
        for class_name in CRITICAL_FEATURES
        if match_ratios[class_name] >= ACCEPTANCE_THRESHOLD
    ]
    complete_targets = [
        class_name for class_name in TARGET_CLASSES if class_name in complete_classes
    ]
    advisory_diagnostics = [
        diagnostic_id
        for diagnostic_id, observation in observations["diagnostics"].items()
        if observation["status"] == "present"
    ]

    result = {
        "candidate_class": candidate_class,
        "routing_score": match_ratios[candidate_class],
        "score_method": SCORE_METHOD_ID,
        "acceptance_threshold": ACCEPTANCE_THRESHOLD,
        "routing_rules_id": ROUTING_RULES_ID,
        "class_match_ratios": match_ratios,
        "complete_classes": complete_classes,
        "advisory_model_diagnostics": advisory_diagnostics,
    }

    if "BOL" in complete_targets and "POD" in complete_targets:
        return {
            **result,
            "action": "UNCERTAIN_NO_FALLBACK",
            "reason": "established_combined_bol_pod",
        }

    if len(complete_targets) > 1:
        return {
            **result,
            "action": "ESCALATE",
            "reason": "multiple_complete_target_combinations",
        }

    if candidate_class == "OTHER":
        if "OTHER" not in complete_classes:
            return {
                **result,
                "action": "ESCALATE",
                "reason": "incomplete_candidate_combination",
            }
        if complete_targets:
            return {
                **result,
                "action": "ESCALATE",
                "reason": "target_class_contradiction",
            }
        return {**result, "action": "ACCEPT", "reason": "complete_candidate_combination"}

    if candidate_class not in complete_targets:
        return {
            **result,
            "action": "ESCALATE",
            "reason": "incomplete_candidate_combination",
        }

    if "OTHER" in complete_classes:
        return {
            **result,
            "action": "ESCALATE",
            "reason": "non_target_contradiction",
        }

    return {**result, "action": "ACCEPT", "reason": "complete_candidate_combination"}
