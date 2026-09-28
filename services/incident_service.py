"""Backend entry point for the implemented investigation stage."""

from agents.incident_investigator import IncidentInvestigator
from agents.remediation_memory import RemediationMemory
from memory.hindsight_client import HindsightClient
from schemas.incident import Incident
from schemas.investigation import InvestigationResult
from schemas.outcome import IncidentMemory, Outcome
from schemas.workflow import Approval, WorkflowResult
from services.remediation_service import remediate_and_retry
from services.verification_service import verify_recovery
from tools.risk_classifier import classify_action
from tools.execution_backend import ExecutionBackend
from llm.client import StructuredLLM
from agents.llm_investigator import LLMInvestigator
from services.ingestion_service import failed_remediation_chunks


def investigate_incident(incident: Incident, client: HindsightClient, llm: StructuredLLM | None = None) -> InvestigationResult:
    """Return a structured recommendation; never execute or persist an action."""
    memory = RemediationMemory(client)
    return (LLMInvestigator(memory, llm) if llm is not None else IncidentInvestigator(memory)).investigate(incident)


class IncidentWorkflow:
    """Single-process workflow with cached results and idempotent memory writes.

    Approval identities are trusted local inputs, not authenticated credentials.
    This class is synchronous and is not a durable or concurrent job runner.
    """

    def __init__(self, client: HindsightClient, world: ExecutionBackend, llm: StructuredLLM | None = None):
        self.client = client
        self.world = world
        self.llm = llm
        self._pending: dict[str, InvestigationResult] = {}
        self._completed: dict[str, tuple[WorkflowResult, IncidentMemory]] = {}
        self._terminal: dict[str, WorkflowResult] = {}

    def restore_pending(self, incident: Incident, investigation: InvestigationResult) -> None:
        """Restore a pre-execution checkpoint without asking the model again."""
        self.world.validate_incident(incident)
        if investigation.incident_id != incident.incident_id:
            raise ValueError("Pending investigation does not match the incident")
        if incident.incident_id in self._completed or incident.incident_id in self._terminal:
            raise ValueError("Cannot restore a terminal workflow")
        self._pending[incident.incident_id] = investigation.model_copy(deep=True)

    def _store_memory(self, memory: IncidentMemory) -> None:
        self.client.store_incident_memory(memory)
        self.client.store_failed_remediation_chunks(failed_remediation_chunks(memory, "workflow outcome"))

    def run(self, incident: Incident, approval: Approval | None = None) -> WorkflowResult:
        self.world.validate_incident(incident)
        key = incident.incident_id
        if key in self._completed:
            result, memory = self._completed[key]
            # Retrying a failed memory write must not rerun actions.
            self._store_memory(memory)
            result.memory_stored = True
            return result.model_copy(deep=True)
        if key in self._terminal:
            return self._terminal[key].model_copy(deep=True)
        if self.client.get_incident_memory(key) is not None:
            raise ValueError("Incident already exists in memory; use a new incident ID")
        if key not in self._pending:
            self._pending[key] = investigate_incident(incident, self.client, self.llm)
        investigation = self._pending[key]
        result = WorkflowResult(incident_id=key, status="INSUFFICIENT_EVIDENCE",
                                investigation=investigation, simulated=self.world.simulated)
        action = investigation.recommended_action
        if action is None:
            return result.model_copy(deep=True)
        decision = classify_action(incident, action, approval)
        result.decision = decision
        result.approval = approval
        if decision.status != "ALLOWED":
            result.status = decision.status
            if decision.status == "DENIED":
                # A rejected recommendation is still a verified control-plane
                # outcome. Persist it so future investigations can learn that
                # this action was considered and intentionally not executed.
                memory = IncidentMemory(
                    incident=incident.model_copy(deep=True),
                    record_kind="observation", workflow_status="DENIED",
                    root_cause=investigation.likely_root_cause,
                    recommendation=action.model_copy(deep=True),
                    final_resolution="HUMAN_REVIEW DENIED: remediation was not executed",
                )
                self._completed[key] = (result, memory)
                self._store_memory(memory)
                result.memory_stored = True
                self._completed[key] = (result, memory)
                self._terminal[key] = result.model_copy(deep=True)
                self._pending.pop(key, None)
            return result.model_copy(deep=True)
        remediation, retry = remediate_and_retry(incident, action, self.world, approval)
        verification = verify_recovery(incident, self.world)
        result.remediation = remediation
        result.reprocessing = retry
        result.verification = verification
        result.status = verification.result
        # Store observations, not the acknowledgement alone, as verified outcomes.
        fix_result = "SUCCESS" if verification.service_healthy else "FAILED"
        source = "Simulation" if self.world.simulated else "Sandbox connector"
        lesson = (f"{source}: {verification.detail} Tool acknowledgement: {remediation.result}. "
                  "The stored root cause remains the investigator's historical hypothesis.")
        outcomes = [Outcome(
            outcome_id=f"{key}-fix", incident_id=key, action=action.action_name,
            result=fix_result, tool_result=remediation.result,
            risk_level=decision.risk_level, verified=True, lesson_learned=lesson,
        )]
        if retry is not None:
            outcomes.append(Outcome(
                outcome_id=f"{key}-retry", incident_id=key, action=retry.action,
                result=verification.result if verification.operation_recovered else "FAILED",
                tool_result=retry.result, reprocessing_result=retry.result,
                risk_level="LOW", verified=True,
                lesson_learned=f"{source}: retry acknowledgement={retry.result}; {verification.detail}",
            ))
        # Preserve the authoritative risk while leaving recommendation confidence intact.
        stored_action = action.model_copy(update={"risk_level": decision.risk_level})
        memory = IncidentMemory(incident=incident.model_copy(deep=True),
                                root_cause=investigation.likely_root_cause,
                                recommendation=stored_action, outcomes=outcomes,
                                final_resolution=f"{source.upper()} {verification.result}: {verification.detail}",
                                final_outcome=verification.result)
        self._completed[key] = (result, memory)
        self._store_memory(memory)
        result.memory_stored = True
        self._pending.pop(key, None)
        return result.model_copy(deep=True)
