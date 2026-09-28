"""Sandbox connector policy, receipts, replay, and uncertain-call behavior."""

from pathlib import Path
import tempfile
import unittest

from agents.outcome_verifier import OutcomeVerifier
from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from services.incident_service import IncidentWorkflow
from tools.connectors import ConnectorReceiptStore, ConnectorUnavailable, SandboxHTTPConnector
from tools.remediation_tools import execute_remediation


ROOT = Path(__file__).resolve().parents[1]


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        _, self.history, cases = load_datasets(ROOT / "data")
        self.incident = cases[0].incident.model_copy(update={"incident_id": "CONNECTOR-001"})

    @staticmethod
    def response(method, url, payload):
        if method == "GET":
            return {"service_healthy": True, "operation_recovered": True,
                    "detail": "Sandbox health and operation checks passed."}
        action = payload["action"]
        return {"action": action, "result": "SUCCESS", "detail": "Sandbox accepted the operation."}

    def test_policy_execution_receipt_replay_and_verification(self):
        calls = []
        def transport(method, url, payload):
            calls.append((method, url))
            return self.response(method, url, payload)

        store = ConnectorReceiptStore(None)
        connector = SandboxHTTPConnector("http://sandbox.internal", 5, store, transport)
        recommendation = self._recommendation()
        first = execute_remediation(self.incident, recommendation, connector)
        second = execute_remediation(self.incident, recommendation, connector)
        self.assertEqual(first.execution_mode, "connector")
        self.assertFalse(first.receipt_replayed)
        self.assertTrue(second.receipt_replayed)
        self.assertEqual(len(calls), 1)
        verification = OutcomeVerifier().verify(self.incident, connector)
        self.assertEqual(verification.result, "SUCCESS")
        self.assertIn("Sandbox", verification.detail)
        store.close()

    def test_completed_receipt_survives_restart(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".test-connectors-") as directory:
            path = Path(directory) / "receipts.sqlite3"
            first_store = ConnectorReceiptStore(path)
            first = SandboxHTTPConnector("http://sandbox.internal", 5, first_store, self.response)
            result = first.remediate(self.incident, "reset_customer_pin")
            first_store.close()

            reopened = ConnectorReceiptStore(path)
            def must_not_call(*args):
                raise AssertionError("Completed connector operation must be replayed locally")
            second = SandboxHTTPConnector("http://sandbox.internal", 5, reopened, must_not_call)
            replay = second.remediate(self.incident, "reset_customer_pin")
            self.assertEqual(replay.idempotency_key, result.idempotency_key)
            self.assertTrue(replay.receipt_replayed)
            reopened.close()

    def test_complete_workflow_uses_connector_and_stores_observations(self):
        store = ConnectorReceiptStore(None)
        connector = SandboxHTTPConnector("http://sandbox.internal", 5, store, self.response)
        memory = MockHindsightClient()
        seed_memory(memory, self.history)
        result = IncidentWorkflow(memory, connector).run(self.incident)
        self.assertEqual(result.status, "SUCCESS")
        self.assertFalse(result.simulated)
        self.assertEqual(result.remediation.execution_mode, "connector")
        self.assertEqual(result.reprocessing.execution_mode, "connector")
        written = memory.get_incident_memory(self.incident.incident_id)
        self.assertTrue(written.final_resolution.startswith("SANDBOX CONNECTOR SUCCESS"))
        store.close()

    def test_uncertain_call_is_not_repeated(self):
        calls = 0
        def timeout(*args):
            nonlocal calls
            calls += 1
            raise TimeoutError
        store = ConnectorReceiptStore(None)
        connector = SandboxHTTPConnector("http://sandbox.internal", 5, store, timeout)
        with self.assertRaises(ConnectorUnavailable):
            connector.remediate(self.incident, "reset_customer_pin")
        with self.assertRaises(ConnectorUnavailable) as caught:
            connector.remediate(self.incident, "reset_customer_pin")
        self.assertIn("reconciliation", str(caught.exception))
        self.assertEqual(calls, 1)
        store.close()

    def test_uncertain_call_can_be_reconciled_without_reexecution(self):
        def timeout(method, url, payload):
            raise TimeoutError
        store = ConnectorReceiptStore(None)
        connector = SandboxHTTPConnector("http://sandbox.internal", 5, store, timeout)
        with self.assertRaises(ConnectorUnavailable):
            connector.remediate(self.incident, "reset_customer_pin")
        payload = {"incident": self.incident.model_dump(), "action": "reset_customer_pin"}
        key, _ = connector._identity("remediation", payload)
        connector._transport = lambda method, url, body: {
            "state": "COMPLETED",
            "result": {"action": "reset_customer_pin", "result": "SUCCESS",
                        "detail": "Confirmed by sandbox receipt.", "idempotency_key": key},
        }
        reconciled = connector.reconcile(key)
        self.assertEqual(reconciled.idempotency_key, key)
        replay = connector.remediate(self.incident, "reset_customer_pin")
        self.assertTrue(replay.receipt_replayed)
        store.close()

    def test_direct_connector_rejects_wrong_context(self):
        store = ConnectorReceiptStore(None)
        wrong = self.incident.model_copy(update={"service": "database-service"})
        connector = SandboxHTTPConnector("http://sandbox.internal", 5, store, self.response)
        with self.assertRaises(PermissionError):
            connector.remediate(wrong, "reset_customer_pin")
        store.close()

    def _recommendation(self):
        from schemas.remediation import RemediationAction
        return RemediationAction(action_name="reset_customer_pin", description="Reset stale PIN state.",
                                 risk_level="LOW", reason="Historical evidence.", confidence=1.0)


if __name__ == "__main__":
    unittest.main()
