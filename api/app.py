"""FastAPI application factory for UI and demo integrations."""

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from api.models import (ApprovalSubmission, CapabilityResponse, DemoScenarioInfo,
                        DemoWorkflowRequest, HealthResponse)
from api.runtime import ApiRuntime, SCENARIOS
from config import Settings
from memory.hindsight_adapter import HindsightUnavailable
from schemas.incident import Incident
from schemas.ingestion import FailedRemediationSearchResult, IngestionResult
from schemas.investigation import InvestigationResult
from schemas.workflow import WorkflowResult
from services.ingestion_service import IngestionValidationError, SUPPORTED_EXTENSIONS
from services.approval_auth import ApprovalAuthenticationError, ApprovalAuthenticator


def create_app(settings: Settings | None = None, runtime: ApiRuntime | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    runtime = runtime or ApiRuntime(settings)
    app = FastAPI(title="Adaptive Incident Intelligence API", version="0.1.0",
                  description="Typed API for investigation and policy-controlled recovery workflows.")
    app.state.runtime = runtime
    approval_auth = ApprovalAuthenticator(settings.approval_credentials)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.api_cors_origins),
                       allow_credentials=False, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "Authorization"])

    def domain_error(exc: Exception):
        if isinstance(exc, IngestionValidationError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        if isinstance(exc, HindsightUnavailable):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health():
        return HealthResponse(memory_backend=settings.memory_backend, llm_provider=settings.llm_provider,
                              model=settings.llm_model if settings.llm_provider == "ollama" else None,
                              action_backend=settings.action_backend,
                              simulated_actions=settings.action_backend == "simulation")

    @app.get("/api/capabilities", response_model=CapabilityResponse, tags=["system"])
    def capabilities():
        return CapabilityResponse(persistent_memory=settings.memory_backend in {"sqlite", "hindsight"},
                                  live_hindsight=settings.memory_backend == "hindsight",
                                  embedding_provider="hindsight" if settings.memory_backend == "hindsight" else "none",
                                  action_backend=settings.action_backend,
                                  simulated_actions=settings.action_backend == "simulation",
                                  authenticated_approvals=approval_auth.enabled)

    @app.post("/api/memory/uploads", response_model=IngestionResult, status_code=201, tags=["memory"])
    async def upload_memory(file: UploadFile = File(...)):
        filename = file.filename or ""
        suffix = "." + filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Supported formats: JSON, CSV, Markdown, TXT, LOG, and PDF")
        content = await file.read(settings.api_upload_max_bytes + 1)
        await file.close()
        if len(content) > settings.api_upload_max_bytes:
            raise HTTPException(status_code=413, detail="Uploaded file exceeds API_UPLOAD_MAX_BYTES")
        try:
            return await run_in_threadpool(runtime.ingest, content, filename)
        except (ValueError, KeyError, RuntimeError, HindsightUnavailable) as exc:
            domain_error(exc)

    @app.get("/api/memory/failed-remediations", response_model=FailedRemediationSearchResult,
             tags=["memory"])
    def search_failed_remediations(q: str = Query(min_length=1, max_length=1000),
                                   limit: int = Query(default=10, ge=1, le=100)):
        try:
            return runtime.search_failed_remediations(q, limit)
        except (ValueError, KeyError, RuntimeError, HindsightUnavailable) as exc:
            domain_error(exc)

    @app.get("/api/demo/scenarios", response_model=list[DemoScenarioInfo], tags=["demo"])
    def demo_scenarios():
        return list(SCENARIOS)

    @app.post("/api/incidents/investigate", response_model=InvestigationResult, tags=["incidents"])
    def investigate(incident: Incident):
        try:
            return runtime.investigate(incident)
        except (ValueError, KeyError, RuntimeError, HindsightUnavailable) as exc:
            domain_error(exc)

    @app.post("/api/demo/workflows", response_model=WorkflowResult, tags=["demo"])
    def start_demo(request: DemoWorkflowRequest):
        try:
            return runtime.start_demo(request.scenario)
        except (ValueError, KeyError, RuntimeError, HindsightUnavailable) as exc:
            domain_error(exc)

    @app.post("/api/demo/workflows/{incident_id}/approval", response_model=WorkflowResult, tags=["demo"])
    def approve_demo(incident_id: str, submission: ApprovalSubmission,
                     authorization: str | None = Header(default=None)):
        try:
            reviewer = approval_auth.authenticate(authorization, submission.reviewer)
            return runtime.submit_approval(incident_id, submission, reviewer=reviewer)
        except ApprovalAuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
        except (ValueError, KeyError, RuntimeError, HindsightUnavailable) as exc:
            domain_error(exc)

    return app
