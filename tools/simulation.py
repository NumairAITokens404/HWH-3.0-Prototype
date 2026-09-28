"""Isolated in-process world: tool acknowledgements and health are independent."""

from dataclasses import dataclass

from schemas.incident import Incident
from schemas.workflow import SimulationScenario, ToolResult


@dataclass
class _State:
    scenario: SimulationScenario
    remediation: ToolResult | None = None
    reprocessing: ToolResult | None = None
    healthy: bool = False
    recovered: bool = False


class SimulationWorld:
    def __init__(self, scenarios: list[SimulationScenario]):
        self._states: dict[str, _State] = {}
        for scenario in scenarios:
            key = scenario.incident.incident_id
            if key in self._states:
                raise ValueError(f"Duplicate scenario: {key}")
            self._states[key] = _State(scenario=scenario.model_copy(deep=True))

    def _state(self, incident: Incident) -> _State:
        state = self._states.get(incident.incident_id)
        if state is None or state.scenario.incident != incident:
            raise ValueError("A matching explicit simulation scenario is required")
        return state

    def validate_incident(self, incident: Incident) -> None:
        self._state(incident)

    def remediate(self, incident: Incident, action: str) -> ToolResult:
        state = self._state(incident)
        if state.remediation is not None:
            if state.remediation.action != action:
                raise ValueError("Simulation already attempted a different action")
            return state.remediation.model_copy(deep=True)
        success = action == state.scenario.required_action and state.scenario.remediation_succeeds
        state.healthy = success and state.scenario.healthy_after_fix
        state.remediation = ToolResult(action=action, result="SUCCESS" if success else "FAILED",
                                       detail="Simulated remediation acknowledgement; health is checked separately.")
        return state.remediation.model_copy(deep=True)

    def retry(self, incident: Incident) -> ToolResult:
        state = self._state(incident)
        if state.remediation is None or state.remediation.result != "SUCCESS":
            raise ValueError("Cannot retry before successful remediation")
        if state.reprocessing is None:
            action = "retry_job" if incident.job_id else "reprocess_transaction" if incident.transaction_id else "retry_request"
            success = state.scenario.retry_succeeds
            state.recovered = success and state.scenario.recovered_after_retry
            state.reprocessing = ToolResult(action=action, result="SUCCESS" if success else "FAILED",
                                            detail=f"Simulated retry of {state.scenario.operation_id}; recovery is checked separately.")
        return state.reprocessing.model_copy(deep=True)

    def observe(self, incident: Incident) -> tuple[bool, bool]:
        state = self._state(incident)
        return state.healthy, state.recovered
