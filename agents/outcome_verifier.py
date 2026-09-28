"""Verify observed state independently of successful tool acknowledgements."""

from schemas.incident import Incident
from schemas.workflow import VerificationResult
from tools.execution_backend import ExecutionBackend


class OutcomeVerifier:
    def verify(self, incident: Incident, world: ExecutionBackend) -> VerificationResult:
        healthy, recovered, detail = world.observation(incident)
        result = "SUCCESS" if healthy and recovered else "PARTIAL" if healthy or recovered else "FAILED"
        return VerificationResult(result=result, service_healthy=healthy, operation_recovered=recovered,
                                  detail=detail)
