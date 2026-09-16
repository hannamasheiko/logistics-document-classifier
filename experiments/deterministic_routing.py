ROUTING_RULES_ID = "critical-combinations-experimental-v1"

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


def _present(payload: dict, feature_id: str) -> bool:
    return payload["features"][feature_id]["status"] == "present"


def _match_ratio(payload: dict, class_name: str) -> float:
    required = CRITICAL_FEATURES[class_name]
    present_count = sum(_present(payload, feature_id) for feature_id in required)
    return present_count / len(required)


def evaluate_routing(payload: dict) -> dict:
    candidate_class = payload["candidate_class"]
    match_ratios = {
        class_name: _match_ratio(payload, class_name)
        for class_name in CRITICAL_FEATURES
    }
    complete_classes = [
        class_name
        for class_name in CRITICAL_FEATURES
        if match_ratios[class_name] == 1.0
    ]
    complete_targets = [
        class_name for class_name in TARGET_CLASSES if class_name in complete_classes
    ]
    advisory_diagnostics = [
        diagnostic_id
        for diagnostic_id, observation in payload["diagnostics"].items()
        if observation["status"] == "present"
    ]

    result = {
        "candidate_class": candidate_class,
        "candidate_match_ratio": match_ratios[candidate_class],
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
