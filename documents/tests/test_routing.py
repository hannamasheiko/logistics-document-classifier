import unittest

from documents.ai.classification import DIAGNOSTIC_IDS, FEATURE_IDS
from documents.services.routing import (
    ACCEPTANCE_THRESHOLD,
    ROUTING_RULES_ID,
    SCORE_METHOD_ID,
    evaluate_routing,
)


def make_observations(candidate_class, present_features=(), present_diagnostics=()):
    return {
        "candidate_class": candidate_class,
        "features": {
            feature_id: {
                "status": "present" if feature_id in present_features else "absent",
                "evidence": "source evidence" if feature_id in present_features else None,
            }
            for feature_id in FEATURE_IDS
        },
        "diagnostics": {
            diagnostic_id: {
                "status": "present" if diagnostic_id in present_diagnostics else "absent",
                "evidence": "source evidence" if diagnostic_id in present_diagnostics else None,
            }
            for diagnostic_id in DIAGNOSTIC_IDS
        },
    }


class RoutingTests(unittest.TestCase):
    def test_frozen_ge_settings(self):
        self.assertEqual(ROUTING_RULES_ID, "critical-combinations-primary-v1")
        self.assertEqual(SCORE_METHOD_ID, "critical-feature-coverage-v1")
        self.assertEqual(ACCEPTANCE_THRESHOLD, 1.0)

    def test_accepts_complete_candidate_combination(self):
        observations = make_observations(
            "BOL",
            present_features=(
                "bol_identity",
                "bol_transport_obligation",
                "bol_shipment_structure",
            ),
        )

        result = evaluate_routing(observations)

        self.assertEqual(result["action"], "ACCEPT")
        self.assertEqual(result["reason"], "complete_candidate_combination")
        self.assertEqual(result["candidate_class"], "BOL")
        self.assertEqual(result["routing_score"], 1.0)
        self.assertEqual(result["complete_classes"], ["BOL"])

    def test_unresolved_observation_escalates_without_becoming_other(self):
        observations = make_observations(
            "INVOICE",
            present_features=("transport_invoice_identity",),
        )

        result = evaluate_routing(observations)

        self.assertEqual(result["action"], "ESCALATE")
        self.assertEqual(result["reason"], "incomplete_candidate_combination")
        self.assertEqual(result["candidate_class"], "INVOICE")
        self.assertNotEqual(result["action"], "ACCEPT")

    def test_all_features_absent_does_not_default_to_other(self):
        observations = make_observations("INVOICE")

        result = evaluate_routing(observations)

        self.assertEqual(result["action"], "ESCALATE")
        self.assertEqual(result["reason"], "incomplete_candidate_combination")
        self.assertEqual(result["candidate_class"], "INVOICE")
        self.assertEqual(result["complete_classes"], [])

    def test_established_combined_bol_pod_is_uncertain_without_fallback(self):
        observations = make_observations(
            "BOL",
            present_features=(
                "bol_identity",
                "bol_transport_obligation",
                "bol_shipment_structure",
                "pod_identity",
                "completed_delivery_event",
                "recipient_acknowledgement",
            ),
        )

        result = evaluate_routing(observations)

        self.assertEqual(result["action"], "UNCERTAIN_NO_FALLBACK")
        self.assertEqual(result["reason"], "established_combined_bol_pod")
        # This priority is evaluated before any acceptance/escalation check, so
        # adding a fallback path later cannot route established ambiguity to it.
        self.assertNotIn(result["action"], {"ACCEPT", "ESCALATE"})

    def test_multiple_complete_target_combinations_escalate_despite_full_candidate_score(self):
        observations = make_observations(
            "BOL",
            present_features=(
                "bol_identity",
                "bol_transport_obligation",
                "bol_shipment_structure",
                "transport_invoice_identity",
                "transport_charge_breakdown",
                "payment_obligation",
            ),
        )

        result = evaluate_routing(observations)

        self.assertEqual(result["routing_score"], 1.0)
        self.assertEqual(result["action"], "ESCALATE")
        self.assertEqual(result["reason"], "multiple_complete_target_combinations")

    def test_other_requires_positive_combination_and_no_target_contradiction(self):
        accepted = make_observations(
            "OTHER",
            present_features=("non_target_identity", "non_target_primary_purpose"),
        )
        contradicted = make_observations(
            "OTHER",
            present_features=(
                "non_target_identity",
                "non_target_primary_purpose",
                "transport_invoice_identity",
                "transport_charge_breakdown",
                "payment_obligation",
            ),
        )

        accepted_result = evaluate_routing(accepted)
        contradicted_result = evaluate_routing(contradicted)

        self.assertEqual(accepted_result["action"], "ACCEPT")
        self.assertEqual(contradicted_result["action"], "ESCALATE")
        self.assertEqual(contradicted_result["reason"], "target_class_contradiction")

    def test_target_candidate_contradicted_by_complete_other_escalates(self):
        observations = make_observations(
            "INVOICE",
            present_features=(
                "transport_invoice_identity",
                "transport_charge_breakdown",
                "payment_obligation",
                "non_target_identity",
                "non_target_primary_purpose",
            ),
        )

        result = evaluate_routing(observations)

        self.assertEqual(result["action"], "ESCALATE")
        self.assertEqual(result["reason"], "non_target_contradiction")

    def test_model_diagnostics_are_advisory_and_do_not_override_complete_combination(self):
        observations = make_observations(
            "POD",
            present_features=(
                "pod_identity",
                "completed_delivery_event",
                "recipient_acknowledgement",
            ),
            present_diagnostics=("contradictory_evidence", "multiple_target_purposes"),
        )

        result = evaluate_routing(observations)

        self.assertEqual(result["action"], "ACCEPT")
        self.assertEqual(
            set(result["advisory_model_diagnostics"]),
            {"contradictory_evidence", "multiple_target_purposes"},
        )


if __name__ == "__main__":
    unittest.main()
