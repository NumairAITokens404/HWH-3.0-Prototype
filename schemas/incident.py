"""Validated incident inputs and held-out dataset cases."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Incident(Schema):
    incident_id: NonEmpty
    service: NonEmpty
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    symptoms: list[NonEmpty] = Field(min_length=1)
    environment: NonEmpty
    error_code: NonEmpty | None = None
    error_message: NonEmpty | None = None
    customer_id: NonEmpty | None = None
    transaction_id: NonEmpty | None = None
    job_id: NonEmpty | None = None
    recent_change: NonEmpty | None = None


class EvaluationCase(Schema):
    """Labels stay outside Incident and must never seed historical memory."""

    incident: Incident
    expected_root_cause: NonEmpty
    expected_action: NonEmpty
    relevant_incident_ids: list[NonEmpty] = Field(min_length=1)
    actions_to_avoid_before_remediation: list[NonEmpty] = Field(min_length=1)
