"""Authorized entry point for mock remediation."""

from schemas.incident import Incident
from schemas.remediation import RemediationAction
from schemas.workflow import Approval, ToolResult
from tools.risk_classifier import classify_action
from tools.simulation import SimulationWorld


def execute_remediation(incident: Incident, action: RemediationAction, world: SimulationWorld,
                        approval: Approval | None = None) -> ToolResult:
    if classify_action(incident, action, approval).status != "ALLOWED":
        raise PermissionError("Remediation is not authorized by the simulation policy")
    return world.remediate(incident, action.action_name)
