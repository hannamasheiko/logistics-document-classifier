import unittest

from experiments.deterministic_routing import ROUTING_RULES_ID, evaluate_routing
from experiments.primary_confidence import DIAGNOSTIC_IDS, FEATURE_IDS


class DeterministicRoutingTests(unittest.TestCase):
    def test_g1_approved_routing_rules_identifier_is_frozen(self):
        self.assertEqual(ROUTING_RULES_ID, "critical-combinations-experimental-v1")

    def make_payload(self, candidate_class, present_features=(), present_diagnostics=()):
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

    def test_accepts_complete_candidate_combination_despite_isolated_other_features(self):
        payload = self.make_payload(
            "POD",
            present_features=(
                "pod_identity",
                "completed_delivery_event",
                "recipient_acknowledgement",
                "bol_shipment_structure",
            ),
        )

        result = evaluate_routing(payload)

        self.assertEqual(result["action"], "ACCEPT")
        self.assertEqual(result["candidate_match_ratio"], 1.0)
        self.assertEqual(result["complete_classes"], ["POD"])

    def test_escalates_when_candidate_critical_combination_is_incomplete(self):
        payload = self.make_payload(
            "INVOICE",
            present_features=("transport_invoice_identity", "payment_obligation"),
        )

        result = evaluate_routing(payload)

        self.assertEqual(result["action"], "ESCALATE")
        self.assertEqual(result["reason"], "incomplete_candidate_combination")
        self.assertEqual(result["candidate_match_ratio"], 2 / 3)

    def test_combined_bol_pod_is_uncertain_without_fallback(self):
        payload = self.make_payload(
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

        result = evaluate_routing(payload)

        self.assertEqual(result["action"], "UNCERTAIN_NO_FALLBACK")
        self.assertEqual(result["reason"], "established_combined_bol_pod")

    def test_other_requires_positive_other_combination_and_no_complete_target(self):
        accepted = self.make_payload(
            "OTHER",
            present_features=(
                "non_target_identity",
                "non_target_primary_purpose",
                "transport_charge_breakdown",
                "payment_obligation",
            ),
        )
        contradicted = self.make_payload(
            "OTHER",
            present_features=(
                "non_target_identity",
                "non_target_primary_purpose",
                "transport_invoice_identity",
                "transport_charge_breakdown",
                "payment_obligation",
            ),
        )

        self.assertEqual(evaluate_routing(accepted)["action"], "ACCEPT")
        self.assertEqual(evaluate_routing(contradicted)["action"], "ESCALATE")
        self.assertEqual(
            evaluate_routing(contradicted)["reason"],
            "target_class_contradiction",
        )

    def test_model_diagnostics_are_reported_but_do_not_override_complete_rules(self):
        payload = self.make_payload(
            "OTHER",
            present_features=("non_target_identity", "non_target_primary_purpose"),
            present_diagnostics=("multiple_target_purposes",),
        )

        result = evaluate_routing(payload)

        self.assertEqual(result["action"], "ACCEPT")
        self.assertEqual(result["advisory_model_diagnostics"], ["multiple_target_purposes"])


if __name__ == "__main__":
    unittest.main()
