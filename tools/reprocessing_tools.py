"""Retry only after the simulator records successful remediation."""

from schemas.incident import Incident
from schemas.workflow import ToolResult
from tools.execution_backend import ExecutionBackend


def reprocess_operation(incident: Incident, world: ExecutionBackend) -> ToolResult:
    return world.retry(incident)
