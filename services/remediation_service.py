"""Execute a permitted simulated fix and retry only after tool success."""

from agents.auto_remediation import AutoRemediationAgent
from agents.reprocessing import ReprocessingAgent
from schemas.incident import Incident
from schemas.remediation import RemediationAction
from schemas.workflow import Approval, ToolResult
from tools.execution_backend import ExecutionBackend


def remediate_and_retry(incident: Incident, action: RemediationAction, world: ExecutionBackend,
                        approval: Approval | None = None) -> tuple[ToolResult, ToolResult | None]:
    remediation = AutoRemediationAgent().execute(incident, action, world, approval)
    retry = ReprocessingAgent().execute(incident, world) if remediation.result == "SUCCESS" else None
    return remediation, retry
