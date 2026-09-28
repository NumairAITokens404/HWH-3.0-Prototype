"""Verify observed state independently of successful tool acknowledgements."""

from schemas.incident import Incident
from schemas.workflow import VerificationResult
from tools.simulation import SimulationWorld


class OutcomeVerifier:
    def verify(self, incident: Incident, world: SimulationWorld) -> VerificationResult:
        healthy, recovered = world.observe(incident)
        result = "SUCCESS" if healthy and recovered else "PARTIAL" if healthy or recovered else "FAILED"
        return VerificationResult(result=result, service_healthy=healthy, operation_recovered=recovered,
                                  detail=f"Observed service_healthy={healthy}, operation_recovered={recovered} in the simulator.")
