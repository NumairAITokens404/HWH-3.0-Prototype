"""Recorded outcomes preserve ordered attempts, including failed fixes."""

from typing import Literal

from pydantic import Field, model_validator

from schemas.incident import Incident, NonEmpty, Schema
from schemas.remediation import RemediationAction, RiskLevel

Result = Literal["SUCCESS", "FAILED", "PARTIAL"]


class Outcome(Schema):
    outcome_id: NonEmpty
    incident_id: NonEmpty
    action: NonEmpty
    result: Result
    reprocessing_result: Result | None = None
    lesson_learned: NonEmpty
    risk_level: RiskLevel
    verified: bool
    resolution_time_minutes: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class IncidentMemory(Schema):
    incident: Incident
    root_cause: NonEmpty | None = None
    recommendation: RemediationAction | None = None
    outcomes: list[Outcome] = Field(default_factory=list)
    final_resolution: NonEmpty | None = None

    @model_validator(mode="after")
    def validate_outcomes(self):
        ids = [outcome.outcome_id for outcome in self.outcomes]
        if len(ids) != len(set(ids)):
            raise ValueError("Outcome IDs must be unique within an incident")
        if any(item.incident_id != self.incident.incident_id for item in self.outcomes):
            raise ValueError("Outcome incident_id must match its incident")
        return self
