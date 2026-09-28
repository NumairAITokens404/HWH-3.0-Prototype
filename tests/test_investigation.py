"""Test recommendations, abstention, and the boundary before execution."""

from pathlib import Path
import unittest

from agents.remediation_memory import RemediationMemory
from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from services.incident_service import investigate_incident


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        _, self.history, self.cases = load_datasets(Path(__file__).resolve().parents[1] / "data")

    def investigate(self, records=None, incident=None):
        client = MockHindsightClient()
        seed_memory(client, self.history if records is None else records)
        return investigate_incident(incident or self.cases[0].incident, client)

    def test_recommends_expected_fix_for_all_held_out_cases(self):
        for case in self.cases:
            with self.subTest(incident=case.incident.incident_id):
                result = self.investigate(incident=case.incident)
                self.assertEqual(result.status, "RECOMMENDATION_READY")
                self.assertEqual(result.recommended_action.action_name, case.expected_action)
                # Root-cause wording is generated from recalled evidence and may
                # be less specific than the independently authored label.
                self.assertTrue(result.likely_root_cause)
                self.assertFalse(result.execution_authorized)
                self.assertGreater(result.recommended_action.confidence, 0)
                self.assertLess(result.recommended_action.confidence, 1)

    def test_counts_failures_and_successes_without_losing_order(self):
        client = MockHindsightClient()
        seed_memory(client, self.history)
        analysis = RemediationMemory(client).analyze(self.cases[0].incident)
        retry = next(item for item in analysis.actions if item.action == "reprocess_transaction")
        self.assertEqual((retry.failed, retry.successful), (2, 2))
        self.assertEqual(len(analysis.evidence), 2)  # Staging incident is excluded.
        self.assertEqual([item.result for item in analysis.evidence[0].outcomes], ["FAILED", "SUCCESS", "SUCCESS"])

    def test_empty_memory_and_missing_error_abstain(self):
        self.assertEqual(self.investigate(records=[]).status, "INSUFFICIENT_EVIDENCE")
        query = self.cases[0].incident.model_copy(update={"error_code": None})
        self.assertIsNone(self.investigate(incident=query).recommended_action)

    def test_wrong_service_environment_or_error_abstains(self):
        for field, value in (("service", "other"), ("environment", "development"), ("error_code", "OTHER")):
            query = self.cases[0].incident.model_copy(update={field: value})
            self.assertIsNone(self.investigate(incident=query).recommended_action)

    def test_unverified_partial_or_failed_fix_cannot_support_recommendation(self):
        for field, value in (("verified", False), ("result", "PARTIAL"), ("result", "FAILED")):
            record = self.history[0].model_copy(deep=True)
            setattr(record.outcomes[1], field, value)
            result = self.investigate(records=[record])
            self.assertIsNone(result.recommended_action)

    def test_failed_or_unverified_reprocessing_abstains(self):
        for field, value in (("verified", False), ("reprocessing_result", "FAILED"), ("result", "PARTIAL")):
            record = self.history[0].model_copy(deep=True)
            setattr(record.outcomes[-1], field, value)
            self.assertIsNone(self.investigate(records=[record]).recommended_action)

    def test_contradictory_fix_history_blocks_recommendation(self):
        record = self.history[1].model_copy(deep=True)
        record.outcomes[1].result = "FAILED"
        self.assertIsNone(self.investigate(records=[self.history[0], record]).recommended_action)

    def test_conflicting_or_missing_root_cause_abstains(self):
        for cause in (None, "different cause"):
            record = self.history[1].model_copy(deep=True)
            record.root_cause = cause
            result = self.investigate(records=[self.history[0], record])
            self.assertIsNone(result.recommended_action)
            self.assertIn("root causes", result.reasoning)

    def test_equally_supported_fixes_abstain(self):
        record = self.history[1].model_copy(deep=True)
        record.outcomes[1].action = "different_fix"
        self.assertIsNone(self.investigate(records=[self.history[0], record]).recommended_action)

    def test_risk_is_conservative_and_never_authorizes_execution(self):
        record = self.history[1].model_copy(deep=True)
        record.outcomes[1].risk_level = "HIGH"
        result = self.investigate(records=[self.history[0], record])
        self.assertEqual(result.recommended_action.risk_level, "HIGH")
        self.assertFalse(result.execution_authorized)

    def test_investigation_has_no_memory_write_side_effects(self):
        client = MockHindsightClient()
        seed_memory(client, self.history)
        query = self.cases[0].incident
        before = client.retrieve_similar_incidents(query)
        investigate_incident(query, client)
        self.assertEqual(before, client.retrieve_similar_incidents(query))
        with self.assertRaises(KeyError):
            client.retrieve_failed_actions(query.incident_id)


if __name__ == "__main__":
    unittest.main()
