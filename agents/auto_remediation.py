"""Deterministic orchestration over authorized simulated remediation tools."""

from schemas.incident import Incident
from schemas.remediation import RemediationAction
from schemas.workflow import Approval, ToolResult
from tools.remediation_tools import execute_remediation
from tools.execution_backend import ExecutionBackend


class AutoRemediationAgent:
    def execute(self, incident: Incident, action: RemediationAction, world: ExecutionBackend,
                approval: Approval | None = None) -> ToolResult:
        return execute_remediation(incident, action, world, approval)
