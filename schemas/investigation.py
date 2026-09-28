"""Structured evidence and recommendation output for the investigation stage."""

from typing import Literal

from pydantic import Field

from schemas.incident import NonEmpty, Schema
from schemas.outcome import Outcome
from schemas.remediation import RemediationAction
from schemas.llm import LLMProposal


class HistoricalEvidence(Schema):
    incident_id: NonEmpty
    similarity: float = Field(ge=0, le=1)
    root_cause: NonEmpty | None
    outcomes: list[Outcome]


class ActionSummary(Schema):
    action: NonEmpty
    successful: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    partial: int = Field(default=0, ge=0)
    unverified: int = Field(default=0, ge=0)


class MemoryAnalysis(Schema):
    evidence: list[HistoricalEvidence] = Field(default_factory=list)
    actions: list[ActionSummary] = Field(default_factory=list)


class InvestigationResult(Schema):
    incident_id: NonEmpty
    status: Literal["RECOMMENDATION_READY", "INSUFFICIENT_EVIDENCE"]
    likely_root_cause: NonEmpty | None = None
    recommended_action: RemediationAction | None = None
    reasoning: NonEmpty
    historical_evidence: list[HistoricalEvidence] = Field(default_factory=list)
    action_summary: list[ActionSummary] = Field(default_factory=list)
    execution_authorized: Literal[False] = False
    method: Literal["deterministic_history_baseline", "llm_grounded", "deterministic_fallback"] = "deterministic_history_baseline"
    model_proposal: LLMProposal | None = None
    model_name: str | None = None
    fallback_reason: str | None = None
    llm_latency_ms: float | None = Field(default=None, ge=0)
