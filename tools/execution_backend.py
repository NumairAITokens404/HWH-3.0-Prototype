"""Execution boundary shared by the simulator and sandbox connectors."""

from typing import Protocol

from schemas.incident import Incident
from schemas.workflow import ToolResult


class ExecutionBackend(Protocol):
    simulated: bool

    def validate_incident(self, incident: Incident) -> None: ...
    def remediate(self, incident: Incident, action: str) -> ToolResult: ...
    def retry(self, incident: Incident) -> ToolResult: ...
    def observation(self, incident: Incident) -> tuple[bool, bool, str]: ...
