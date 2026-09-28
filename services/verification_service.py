"""Backend entry point for independent simulated health observations."""

from agents.outcome_verifier import OutcomeVerifier
from schemas.incident import Incident
from schemas.workflow import VerificationResult
from tools.simulation import SimulationWorld


def verify_recovery(incident: Incident, world: SimulationWorld) -> VerificationResult:
    return OutcomeVerifier().verify(incident, world)
