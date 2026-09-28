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
from schemas.ingestion import FailedRemediationSearchResult, IngestionResult
from schemas.investigation import InvestigationResult
from schemas.workflow import Approval, SimulationScenario, WorkflowResult
from services.incident_service import IncidentWorkflow, investigate_incident
from services.ingestion_service import ingest_incident_history
from services.workflow_store import WorkflowStore
from tools.connectors import ConnectorReceiptStore, SandboxHTTPConnector
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
    scenario: SimulationScenario
    workflow: IncidentWorkflow


class ApiRuntime:
    """Own initialized dependencies and bounded in-process demo workflow state."""

    def __init__(self, settings: Settings, max_active_runs: int = 100):
        if max_active_runs < 1:
            raise ValueError("max_active_runs must be positive")
        self.settings = settings
        _, history, self.cases = load_datasets(settings.data_dir)
        self.history = history
        self._memory_ids = {record.incident.incident_id for record in history}
        self.memory = create_memory_client(settings)
        seed_memory(self.memory, history)
        self.llm = create_llm(settings)
        self.max_active_runs = max_active_runs
        self._runs: dict[str, _Run] = {}
        self._lock = RLock()
        self.workflow_store = WorkflowStore(settings.workflow_db_path)
        self.connector_receipts = (ConnectorReceiptStore(settings.connector_receipt_db_path)
                                   if settings.action_backend == "connector" else None)
        self._restore_pending_runs()

    def _execution_backend(self, scenario: SimulationScenario):
        if self.settings.action_backend == "simulation":
            return SimulationWorld([scenario])
        return SandboxHTTPConnector(self.settings.connector_base_url, self.settings.connector_timeout,
                                    self.connector_receipts, api_key=self.settings.connector_api_key)

    def _restore_pending_runs(self) -> None:
        records = self.workflow_store.pending_runs(self.max_active_runs + 1)
        if len(records) > self.max_active_runs:
            raise RuntimeError("Persisted workflow capacity exceeds max_active_runs")
        for record in records:
            scenario = record.scenario
            workflow = IncidentWorkflow(self.memory, self._execution_backend(scenario), self.llm)
            workflow.restore_pending(scenario.incident, record.result.investigation)
            self._runs[record.incident_id] = _Run(scenario=scenario, workflow=workflow)

    def _audit_start(self, scenario: SimulationScenario, result: WorkflowResult) -> None:
        incident_id = result.incident_id
        self.workflow_store.append_event(incident_id, "INCIDENT_RECEIVED", {
            "service": scenario.incident.service, "severity": scenario.incident.severity,
        })
        self.workflow_store.append_event(incident_id, "INVESTIGATION_COMPLETED", {
            "method": result.investigation.method,
            "confidence": (result.investigation.recommended_action.confidence
                           if result.investigation.recommended_action is not None else None),
        })
        if result.investigation.recommended_action is not None:
            self.workflow_store.append_event(incident_id, "ACTION_RECOMMENDED", {
                "action": result.investigation.recommended_action.action_name,
            })
        if result.status == "HUMAN_APPROVAL_REQUIRED":
            self.workflow_store.append_event(incident_id, "APPROVAL_REQUESTED", {
                "request_id": result.decision.request_id, "risk_level": result.decision.risk_level,
            })
        else:
            self._audit_execution(result)

    def _audit_execution(self, result: WorkflowResult) -> None:
        incident_id = result.incident_id
        if result.remediation is not None:
            self.workflow_store.append_event(incident_id, "REMEDIATION_EXECUTED", {
                "action": result.remediation.action, "result": result.remediation.result,
            })
        if result.reprocessing is not None:
            self.workflow_store.append_event(incident_id, "REPROCESSING_EXECUTED", {
                "action": result.reprocessing.action, "result": result.reprocessing.result,
            })
        if result.verification is not None:
            self.workflow_store.append_event(incident_id, "OUTCOME_VERIFIED", {
                "result": result.verification.result,
                "service_healthy": result.verification.service_healthy,
                "operation_recovered": result.verification.operation_recovered,
            })
        if result.memory_stored:
            self.workflow_store.append_event(incident_id, "MEMORY_UPDATED", {})

    def investigate(self, incident: Incident) -> InvestigationResult:
        with self._lock:
            return investigate_incident(incident, self.memory, self.llm)

    def ingest(self, content: bytes, filename: str) -> IngestionResult:
        with self._lock:
            result = ingest_incident_history(content, filename, self.memory, self.settings.memory_backend)
            self._memory_ids.update(result.incident_ids)
            return result

    def memory_records(self):
        with self._lock:
            return [record for incident_id in sorted(self._memory_ids)
                    if (record := self.memory.get_incident_memory(incident_id)) is not None]

    def case(self, incident_id: str):
        case = next((item for item in self.cases if item.incident.incident_id == incident_id), None)
        if case is None:
            raise KeyError("Unknown incident")
        return case

    def case_result(self, incident_id: str) -> WorkflowResult | None:
        record = self.workflow_store.get_run(incident_id)
        return record.result if record else None

    def start_case(self, incident_id: str) -> WorkflowResult:
        with self._lock:
            existing = self.workflow_store.get_run(incident_id)
            if existing is not None:
                return existing.result
            if len(self._runs) >= self.max_active_runs:
                raise RuntimeError("Demo workflow capacity reached; restart the API to clear local state")
            case = self.case(incident_id)
            incident = case.incident
            operation_id = (incident.transaction_id or incident.job_id or incident.customer_id
                            or "UI-OP-" + incident.incident_id)
            scenario = SimulationScenario(incident=incident, operation_id=operation_id,
                                          required_action=case.expected_action)
            workflow = IncidentWorkflow(self.memory, self._execution_backend(scenario), self.llm)
            run = _Run(scenario=scenario, workflow=workflow)
            result = workflow.run(incident)
            if result.status == "HUMAN_APPROVAL_REQUIRED":
                self._runs[incident_id] = run
                state = "PENDING_APPROVAL"
            elif result.status in {"SUCCESS", "FAILED", "PARTIAL"}:
                state = "COMPLETED"
            else:
                state = "TERMINAL"
            self.workflow_store.save_run(scenario, result, state)
            self._audit_start(scenario, result)
            if result.memory_stored:
                self._memory_ids.add(incident_id)
            return result

    def search_failed_remediations(self, query: str, limit: int) -> FailedRemediationSearchResult:
        with self._lock:
            matches = self.memory.retrieve_failed_remediation_chunks(query, limit)
        return FailedRemediationSearchResult(query=query, matches=matches)

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
            workflow = IncidentWorkflow(self.memory, self._execution_backend(scenario), self.llm)
            run = _Run(scenario=scenario, workflow=workflow)
            result = workflow.run(scenario.incident)
            if result.status == "HUMAN_APPROVAL_REQUIRED":
                self._runs[scenario.incident.incident_id] = run
                state = "PENDING_APPROVAL"
            elif result.status == "DENIED":
                state = "DENIED"
            elif result.status in {"SUCCESS", "FAILED", "PARTIAL"}:
                state = "COMPLETED"
            else:
                state = "TERMINAL"
            self.workflow_store.save_run(scenario, result, state)
            self._audit_start(scenario, result)
            return result

    def submit_approval(self, incident_id: str, submission: ApprovalSubmission,
                        reviewer: str | None = None) -> WorkflowResult:
        with self._lock:
            reviewer = reviewer or submission.reviewer
            if not reviewer:
                raise ValueError("Reviewer is required")
            run = self._runs.get(incident_id)
            if run is None:
                raise KeyError("Unknown or expired demo workflow")
            approval = Approval(request_id=submission.request_id, approved=submission.approved,
                                reviewer=reviewer)
            self.workflow_store.append_event(incident_id, "APPROVAL_SUBMITTED", {
                "request_id": submission.request_id, "approved": submission.approved,
                "reviewer": reviewer,
            })
            persisted = self.workflow_store.get_run(incident_id)
            expected = persisted.result.decision.request_id if persisted and persisted.result.decision else None
            if submission.approved and submission.request_id == expected:
                self.workflow_store.save_run(run.scenario, persisted.result, "EXECUTING")
            result = run.workflow.run(run.scenario.incident, approval)
            if result.status == "BLOCKED":
                self.workflow_store.append_event(incident_id, "APPROVAL_BLOCKED", {
                    "reason": result.decision.reason,
                })
                self.workflow_store.save_run(run.scenario, result, "PENDING_APPROVAL")
                return result
            if result.status == "DENIED":
                state = "DENIED"
                self.workflow_store.append_event(incident_id, "DENIED", {"reviewer": reviewer})
            else:
                state = "COMPLETED" if result.status in {"SUCCESS", "FAILED", "PARTIAL"} else "TERMINAL"
                self.workflow_store.append_event(incident_id, "APPROVED", {"reviewer": reviewer})
                self._audit_execution(result)
            self.workflow_store.save_run(run.scenario, result, state)
            if result.memory_stored:
                self._memory_ids.add(incident_id)
            if result.status != "BLOCKED":
                self._runs.pop(incident_id, None)
            return result
