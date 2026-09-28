"""Deterministic agent for retrying the failed simulated operation."""

from schemas.incident import Incident
from schemas.workflow import ToolResult
from tools.reprocessing_tools import reprocess_operation
from tools.simulation import SimulationWorld


class ReprocessingAgent:
    def execute(self, incident: Incident, world: SimulationWorld) -> ToolResult:
        return reprocess_operation(incident, world)
