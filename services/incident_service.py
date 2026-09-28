"""Backend entry point for the implemented investigation stage."""

from agents.incident_investigator import IncidentInvestigator
from agents.remediation_memory import RemediationMemory
from memory.hindsight_client import HindsightClient
from schemas.incident import Incident
from schemas.investigation import InvestigationResult


def investigate_incident(incident: Incident, client: HindsightClient) -> InvestigationResult:
    """Return a structured recommendation; never execute or persist an action."""
    return IncidentInvestigator(RemediationMemory(client)).investigate(incident)
