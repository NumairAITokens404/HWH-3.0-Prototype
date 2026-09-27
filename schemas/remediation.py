"""Recommendation contracts only; no action execution in Phase 1."""

from typing import Literal

from pydantic import Field

from schemas.incident import NonEmpty, Schema

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class RemediationAction(Schema):
    action_name: NonEmpty
    description: NonEmpty
    risk_level: RiskLevel
    reason: NonEmpty
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
