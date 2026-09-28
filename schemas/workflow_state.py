"""Durable workflow and audit-log contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from schemas.incident import NonEmpty, Schema
from schemas.workflow import SimulationScenario, WorkflowResult


WorkflowState = Literal["PENDING_APPROVAL", "EXECUTING", "COMPLETED", "DENIED", "TERMINAL"]
AuditEventType = Literal[
    "INCIDENT_RECEIVED",
    "INVESTIGATION_COMPLETED",
    "ACTION_RECOMMENDED",
    "APPROVAL_REQUESTED",
    "APPROVAL_SUBMITTED",
    "APPROVAL_BLOCKED",
    "APPROVED",
    "DENIED",
    "REMEDIATION_EXECUTED",
    "REPROCESSING_EXECUTED",
    "OUTCOME_VERIFIED",
    "MEMORY_UPDATED",
]


class WorkflowRunRecord(Schema):
    incident_id: NonEmpty
    state: WorkflowState
    scenario: SimulationScenario
    result: WorkflowResult
    updated_at: datetime


class AuditEvent(Schema):
    sequence: int = Field(ge=1)
    incident_id: NonEmpty
    event_type: AuditEventType
    occurred_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)
