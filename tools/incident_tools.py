"""Validated JSON inputs for terminal and backend entry points."""

from pathlib import Path
from schemas.incident import Incident
from schemas.workflow import SimulationScenario


def load_incident(path: Path) -> Incident:
    return Incident.model_validate_json(path.read_text(encoding="utf-8-sig"))


def load_scenario(path: Path) -> SimulationScenario:
    return SimulationScenario.model_validate_json(path.read_text(encoding="utf-8-sig"))
