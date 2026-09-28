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
    action_backend: Literal["simulation", "connector"]
    simulated_actions: bool


class CapabilityResponse(Schema):
    investigation: Literal[True] = True
    demo_workflows: Literal[True] = True
    approval_resume: Literal[True] = True
    persistent_memory: bool
    live_hindsight: bool
    file_ingestion: Literal[True] = True
    ingestion_formats: list[Literal["json", "csv", "md", "txt", "log", "pdf"]] = Field(
        default_factory=lambda: ["json", "csv", "md", "txt", "log", "pdf"])
    embedding_provider: Literal["hindsight", "none"]
    action_backend: Literal["simulation", "connector"]
    simulated_actions: bool


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
