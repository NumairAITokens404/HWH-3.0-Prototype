"""Backend entry point for independent simulated health observations."""

from agents.outcome_verifier import OutcomeVerifier
from schemas.incident import Incident
from schemas.workflow import VerificationResult
from tools.execution_backend import ExecutionBackend


def verify_recovery(incident: Incident, world: ExecutionBackend) -> VerificationResult:
    return OutcomeVerifier().verify(incident, world)
