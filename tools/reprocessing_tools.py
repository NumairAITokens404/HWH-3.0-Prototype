"""Retry only after the simulator records successful remediation."""

from schemas.incident import Incident
from schemas.workflow import ToolResult
from tools.simulation import SimulationWorld


def reprocess_operation(incident: Incident, world: SimulationWorld) -> ToolResult:
    return world.retry(incident)
