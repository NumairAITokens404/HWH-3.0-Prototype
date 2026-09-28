"""Public API request and response contracts."""

from typing import Literal

from pydantic import Field

from schemas.incident import NonEmpty, Schema


DemoScenarioName = Literal["low-risk-success", "high-risk-approval", "partial-recovery"]


class HealthResponse(Schema):
    status: Literal["ok"] = "ok"
    memory_backend: NonEmpty
    llm_provider: NonEmpty
    model: str | None = None
    simulated_actions: Literal[True] = True


class CapabilityResponse(Schema):
    investigation: Literal[True] = True
    demo_workflows: Literal[True] = True
    approval_resume: Literal[True] = True
    persistent_memory: bool
    live_hindsight: bool
    file_ingestion: Literal[False] = False
    simulated_actions: Literal[True] = True


class DemoScenarioInfo(Schema):
    name: DemoScenarioName
    title: NonEmpty
    description: NonEmpty
    expected_gate: Literal["AUTO_EXECUTE", "HUMAN_APPROVAL_REQUIRED"]


class DemoWorkflowRequest(Schema):
    scenario: DemoScenarioName


class ApprovalSubmission(Schema):
    request_id: NonEmpty
    approved: bool
    reviewer: NonEmpty = Field(max_length=200)
