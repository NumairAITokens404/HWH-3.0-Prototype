"""Deterministic orchestration over authorized simulated remediation tools."""

from schemas.incident import Incident
from schemas.remediation import RemediationAction
from schemas.workflow import Approval, ToolResult
from tools.remediation_tools import execute_remediation
from tools.simulation import SimulationWorld


class AutoRemediationAgent:
    def execute(self, incident: Incident, action: RemediationAction, world: SimulationWorld,
                approval: Approval | None = None) -> ToolResult:
        return execute_remediation(incident, action, world, approval)
