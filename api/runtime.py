"""Thread-safe application runtime shared by HTTP request handlers."""

from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from api.models import ApprovalSubmission, DemoScenarioInfo, DemoScenarioName
from config import Settings
from llm.client import create_llm
from memory.factory import create_memory_client
from memory.memory_writer import load_datasets, seed_memory
from schemas.incident import Incident
from schemas.investigation import InvestigationResult
from schemas.workflow import Approval, SimulationScenario, WorkflowResult
from services.incident_service import IncidentWorkflow, investigate_incident
from tools.simulation import SimulationWorld


SCENARIOS = (
    DemoScenarioInfo(name="low-risk-success", title="Automatic low-risk recovery",
                     description="Reset a stale simulated PIN state and reprocess the transaction.",
                     expected_gate="AUTO_EXECUTE"),
    DemoScenarioInfo(name="high-risk-approval", title="High-risk rollback approval",
                     description="Pause a database rollback until a reviewer approves it.",
                     expected_gate="HUMAN_APPROVAL_REQUIRED"),
    DemoScenarioInfo(name="partial-recovery", title="Partial recovery",
                     description="Restore service health while the affected transaction retry still fails.",
                     expected_gate="AUTO_EXECUTE"),
)


@dataclass
class _Run:
    incident: Incident
    workflow: IncidentWorkflow


class ApiRuntime:
    """Own initialized dependencies and bounded in-process demo workflow state."""

    def __init__(self, settings: Settings, max_active_runs: int = 100):
        if max_active_runs < 1:
            raise ValueError("max_active_runs must be positive")
        self.settings = settings
        _, history, self.cases = load_datasets(settings.data_dir)
        self.memory = create_memory_client(settings)
        seed_memory(self.memory, history)
        self.llm = create_llm(settings)
        self.max_active_runs = max_active_runs
        self._runs: dict[str, _Run] = {}
        self._lock = RLock()

    def investigate(self, incident: Incident) -> InvestigationResult:
        with self._lock:
            return investigate_incident(incident, self.memory, self.llm)

    def _scenario(self, name: DemoScenarioName) -> SimulationScenario:
        suffix = uuid4().hex[:12]
        if name == "high-risk-approval":
            source = self.cases[2].incident
            incident = source.model_copy(update={"incident_id": f"API-REVIEW-{suffix}"})
            return SimulationScenario(incident=incident, operation_id=f"API-REQ-{suffix}",
                                      required_action="rollback_connection_pool_change")
        source = self.cases[0].incident
        incident = source.model_copy(update={"incident_id": f"API-PIN-{suffix}",
                                             "transaction_id": f"API-TXN-{suffix}"})
        return SimulationScenario(incident=incident, operation_id=incident.transaction_id,
                                  required_action="reset_customer_pin",
                                  retry_succeeds=name != "partial-recovery")

    def start_demo(self, name: DemoScenarioName) -> WorkflowResult:
        with self._lock:
            if len(self._runs) >= self.max_active_runs:
                raise RuntimeError("Demo workflow capacity reached; restart the API to clear local state")
            scenario = self._scenario(name)
            workflow = IncidentWorkflow(self.memory, SimulationWorld([scenario]), self.llm)
            run = _Run(incident=scenario.incident, workflow=workflow)
            result = workflow.run(run.incident)
            if result.status == "HUMAN_APPROVAL_REQUIRED":
                self._runs[scenario.incident.incident_id] = run
            return result

    def submit_approval(self, incident_id: str, submission: ApprovalSubmission) -> WorkflowResult:
        with self._lock:
            run = self._runs.get(incident_id)
            if run is None:
                raise KeyError("Unknown or expired demo workflow")
            approval = Approval(request_id=submission.request_id, approved=submission.approved,
                                reviewer=submission.reviewer)
            result = run.workflow.run(run.incident, approval)
            if result.status != "BLOCKED":
                self._runs.pop(incident_id, None)
            return result
