"""Contracts for local simulation, approval, and verified workflow results."""

from typing import Literal

from schemas.incident import Incident, NonEmpty, Schema
from schemas.investigation import InvestigationResult
from schemas.outcome import Result
from schemas.remediation import RiskLevel


class Approval(Schema):
    request_id: NonEmpty
    approved: bool
    reviewer: NonEmpty


class ActionDecision(Schema):
    status: Literal["ALLOWED", "HUMAN_APPROVAL_REQUIRED", "DENIED", "BLOCKED"]
    action_name: NonEmpty
    risk_level: RiskLevel
    request_id: NonEmpty
    reason: NonEmpty


class SimulationScenario(Schema):
    """Hidden simulator truth, supplied separately from investigator inputs."""

    incident: Incident
    operation_id: NonEmpty
    required_action: NonEmpty
    remediation_succeeds: bool = True
    retry_succeeds: bool = True
    healthy_after_fix: bool = True
    recovered_after_retry: bool = True


class ToolResult(Schema):
    action: NonEmpty
    result: Result
    detail: NonEmpty


class VerificationResult(Schema):
    result: Result
    service_healthy: bool
    operation_recovered: bool
    detail: NonEmpty


class WorkflowResult(Schema):
    incident_id: NonEmpty
    status: Literal["INSUFFICIENT_EVIDENCE", "HUMAN_APPROVAL_REQUIRED", "DENIED", "BLOCKED", "SUCCESS", "FAILED", "PARTIAL"]
    investigation: InvestigationResult
    decision: ActionDecision | None = None
    approval: Approval | None = None
    remediation: ToolResult | None = None
    reprocessing: ToolResult | None = None
    verification: VerificationResult | None = None
    memory_stored: bool = False
    simulated: Literal[True] = True
