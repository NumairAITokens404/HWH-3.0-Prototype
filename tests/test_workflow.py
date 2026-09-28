"""Approval boundaries, simulated failures, verification, and memory feedback."""

from pathlib import Path
import unittest
from unittest.mock import patch

from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from schemas.workflow import Approval, SimulationScenario
from services.incident_service import IncidentWorkflow, investigate_incident
from tools.remediation_tools import execute_remediation
from tools.risk_classifier import classify_action
from tools.simulation import SimulationWorld


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        _, self.history, self.cases = load_datasets(Path(__file__).resolve().parents[1] / "data")
        self.client = MockHindsightClient()
        seed_memory(self.client, self.history)

    def setup_workflow(self, index=0, **changes):
        incident = self.cases[index].incident.model_copy(update={"incident_id": f"RUN-{index}"})
        scenario = SimulationScenario(incident=incident, operation_id=f"SYN-OP-{index}",
                                      required_action=self.cases[index].expected_action, **changes)
        world = SimulationWorld([scenario])
        return incident, world, IncidentWorkflow(self.client, world)

    def test_low_risk_executes_verifies_and_stores(self):
        incident, world, workflow = self.setup_workflow()
        result = workflow.run(incident)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(world.observe(incident), (True, True))
        self.assertTrue(result.memory_stored)
        record = self.client.get_incident_memory(incident.incident_id)
        self.assertEqual([item.result for item in record.outcomes], ["SUCCESS", "SUCCESS"])
        self.assertFalse(result.investigation.execution_authorized)

    def test_medium_and_high_risk_wait_for_matching_approval(self):
        for index in (1, 2, 3, 5):
            incident, world, workflow = self.setup_workflow(index)
            waiting = workflow.run(incident)
            self.assertEqual(waiting.status, "HUMAN_APPROVAL_REQUIRED")
            self.assertEqual(world.observe(incident), (False, False))
            self.assertIsNone(self.client.get_incident_memory(incident.incident_id))
            approval = Approval(request_id=waiting.decision.request_id, approved=True, reviewer="test-reviewer")
            result = workflow.run(incident, approval)
            self.assertEqual(result.status, "SUCCESS")
            self.assertEqual(result.approval.reviewer, "test-reviewer")

    def test_denial_and_mismatched_approval_never_execute(self):
        incident, world, workflow = self.setup_workflow(2)
        waiting = workflow.run(incident)
        denied = Approval(request_id=waiting.decision.request_id, approved=False, reviewer="test-reviewer")
        self.assertEqual(workflow.run(incident, denied).status, "DENIED")
        wrong = denied.model_copy(update={"request_id": "wrong", "approved": True})
        self.assertEqual(workflow.run(incident, wrong).status, "BLOCKED")
        self.assertEqual(world.observe(incident), (False, False))

    def test_policy_ignores_suggested_low_risk_for_high_risk_action(self):
        incident, world, _ = self.setup_workflow(2)
        action = investigate_incident(incident, self.client).recommended_action
        action.risk_level = "LOW"
        self.assertEqual(classify_action(incident, action).risk_level, "HIGH")
        with self.assertRaises(PermissionError):
            execute_remediation(incident, action, world)

    def test_unknown_action_or_wrong_context_blocked(self):
        incident, world, _ = self.setup_workflow()
        action = investigate_incident(incident, self.client).recommended_action
        for name in ("delete_database", "rollback_connection_pool_change"):
            proposed = action.model_copy(update={"action_name": name})
            self.assertEqual(classify_action(incident, proposed).status, "BLOCKED")
            with self.assertRaises(PermissionError):
                execute_remediation(incident, proposed, world)

    def test_approval_does_not_transfer_to_another_incident(self):
        incident, _, _ = self.setup_workflow(2)
        action = investigate_incident(incident, self.client).recommended_action
        decision = classify_action(incident, action)
        approval = Approval(request_id=decision.request_id, approved=True, reviewer="test-reviewer")
        other = incident.model_copy(update={"incident_id": "OTHER"})
        self.assertEqual(classify_action(other, action, approval).status, "BLOCKED")

    def test_failed_remediation_skips_retry_and_is_remembered(self):
        incident, _, workflow = self.setup_workflow(remediation_succeeds=False)
        result = workflow.run(incident)
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(result.reprocessing)
        self.assertEqual(len(self.client.retrieve_failed_actions(incident.incident_id)), 1)

    def test_failed_retry_is_partial_recovery(self):
        incident, _, workflow = self.setup_workflow(retry_succeeds=False)
        result = workflow.run(incident)
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.reprocessing.result, "FAILED")
        record = self.client.get_incident_memory(incident.incident_id)
        self.assertEqual(record.outcomes[-1].result, "FAILED")
        self.assertEqual(record.outcomes[-1].tool_result, "FAILED")
        self.assertEqual(record.final_outcome, "PARTIAL")

    def test_successful_acknowledgements_do_not_prove_recovery(self):
        incident, _, workflow = self.setup_workflow(healthy_after_fix=False, recovered_after_retry=False)
        result = workflow.run(incident)
        self.assertEqual(result.remediation.result, "SUCCESS")
        self.assertEqual(result.reprocessing.result, "SUCCESS")
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(len(self.client.retrieve_failed_actions(incident.incident_id)), 2)

    def test_retry_before_remediation_is_rejected(self):
        incident, world, _ = self.setup_workflow()
        with self.assertRaises(ValueError):
            world.retry(incident)

    def test_repeated_run_is_idempotent_and_returns_a_copy(self):
        incident, world, workflow = self.setup_workflow()
        first = workflow.run(incident)
        with patch.object(world, "remediate", side_effect=AssertionError("Must not execute twice")):
            second = workflow.run(incident)
        self.assertEqual(first, second)
        second.status = "FAILED"
        self.assertEqual(workflow.run(incident).status, "SUCCESS")
        self.assertEqual(len(self.client.get_incident_memory(incident.incident_id).outcomes), 2)

    def test_memory_write_retry_does_not_repeat_actions(self):
        incident, world, workflow = self.setup_workflow()
        with patch.object(self.client, "store_incident_memory", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                workflow.run(incident)
        with patch.object(world, "remediate", side_effect=AssertionError("Must not execute twice")):
            self.assertTrue(workflow.run(incident).memory_stored)

    def test_new_incident_recalls_written_experience(self):
        incident, _, workflow = self.setup_workflow()
        workflow.run(incident)
        later = incident.model_copy(update={"incident_id": "LATER"})
        result = investigate_incident(later, self.client)
        self.assertIn(incident.incident_id, [item.incident_id for item in result.historical_evidence])

    def test_existing_memory_prevents_execution(self):
        record = self.history[0]
        world = SimulationWorld([SimulationScenario(incident=record.incident, operation_id="EXISTING",
                                                    required_action="reset_customer_pin")])
        with self.assertRaises(ValueError):
            IncidentWorkflow(self.client, world).run(record.incident)
        self.assertEqual(world.observe(record.incident), (False, False))

    def test_missing_scenario_is_rejected_before_execution(self):
        with self.assertRaises(ValueError):
            IncidentWorkflow(self.client, SimulationWorld([])).run(self.cases[0].incident)

    def test_insufficient_evidence_has_no_side_effects(self):
        incident, world, _ = self.setup_workflow()
        client = MockHindsightClient()
        result = IncidentWorkflow(client, world).run(incident)
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(world.observe(incident), (False, False))
        self.assertIsNone(client.get_incident_memory(incident.incident_id))


if __name__ == "__main__":
    unittest.main()
