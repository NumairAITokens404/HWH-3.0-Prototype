"""Authorized entry point for mock remediation."""

from schemas.incident import Incident
from schemas.remediation import RemediationAction
from schemas.workflow import Approval, ToolResult
from tools.risk_classifier import classify_action
from tools.execution_backend import ExecutionBackend


def execute_remediation(incident: Incident, action: RemediationAction, world: ExecutionBackend,
                        approval: Approval | None = None) -> ToolResult:
    if classify_action(incident, action, approval).status != "ALLOWED":
        raise PermissionError("Remediation is not authorized by the simulation policy")
    return world.remediate(incident, action.action_name)
