"""Durable approval checkpoints and append-only audit history."""

from pathlib import Path
import tempfile
import unittest

from api.models import ApprovalSubmission
from api.runtime import ApiRuntime
from config import Settings


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPersistenceTests(unittest.TestCase):
    def test_pending_approval_survives_runtime_restart(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".test-workflows-") as directory:
            database = Path(directory) / "workflows.sqlite3"
            settings = Settings(data_dir=ROOT / "data", workflow_db_path=database)
            first = ApiRuntime(settings)
            pending = first.start_demo("high-risk-approval")
            incident_id = pending.incident_id
            request_id = pending.decision.request_id
            self.assertEqual(first.workflow_store.get_run(incident_id).state, "PENDING_APPROVAL")
            first.workflow_store.close()

            restarted = ApiRuntime(settings)
            completed = restarted.submit_approval(
                incident_id, ApprovalSubmission(request_id=request_id, approved=True, reviewer="restart-test"))
            self.assertEqual(completed.status, "SUCCESS")
            self.assertEqual(restarted.workflow_store.get_run(incident_id).state, "COMPLETED")
            event_types = [item.event_type for item in restarted.workflow_store.events_for(incident_id)]
            self.assertEqual(event_types[:4], ["INCIDENT_RECEIVED", "INVESTIGATION_COMPLETED",
                                               "ACTION_RECOMMENDED", "APPROVAL_REQUESTED"])
            self.assertIn("APPROVED", event_types)
            self.assertEqual(event_types[-1], "MEMORY_UPDATED")
            restarted.workflow_store.close()

    def test_terminal_state_cannot_be_reopened(self):
        runtime = ApiRuntime(Settings(data_dir=ROOT / "data"))
        result = runtime.start_demo("low-risk-success")
        record = runtime.workflow_store.get_run(result.incident_id)
        with self.assertRaises(ValueError):
            runtime.workflow_store.save_run(record.scenario, record.result, "PENDING_APPROVAL")
        runtime.workflow_store.close()


if __name__ == "__main__":
    unittest.main()
