# HTTP API for the web platform

[Documentation index](README.md)

The FastAPI layer exposes the existing investigation and simulated workflow services without moving policy into the browser. OpenAPI is the source of truth for generated frontend types.

## Start locally

```powershell
.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API schema. Configure allowed frontend origins with `API_CORS_ORIGINS`; credentials are disabled because this prototype does not implement authentication.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /api/health` | Report configured memory/model providers and the simulation boundary. |
| `GET /api/capabilities` | Tell the UI which integrations are active. |
| `POST /api/memory/uploads` | Validate and ingest JSON, CSV, Markdown, text/log, or text-based PDF incident history. |
| `GET /api/memory/failed-remediations` | Search failed and partial remediation chunks. |
| `GET /api/demo/scenarios` | List server-owned demo scenarios without exposing their hidden expected actions. |
| `POST /api/incidents/investigate` | Return a read-only recommendation for an `Incident`. |
| `POST /api/demo/workflows` | Start a named simulated workflow. |
| `POST /api/demo/workflows/{incident_id}/approval` | Resume a pending workflow with a bound reviewer decision. |

The API generates demo incident IDs. The browser never submits `required_action`, health truth, or expected evaluation labels. Low-risk scenarios finish immediately. High-risk scenarios return `HUMAN_APPROVAL_REQUIRED` and a `decision.request_id` that must be returned with the reviewer decision.

## Approval lifecycle

- A mismatched request ID returns `BLOCKED`; the correct request may still be submitted.
- A bound rejection returns `DENIED` and permanently closes the run.
- A successful or denied run is removed from the active registry while its checkpoint and audit history remain durable.
- Pending approvals survive API restarts through `WORKFLOW_DB_PATH`; the original investigation is restored without another model call.
- An approved action is checkpointed as `EXECUTING` before it runs. Ambiguous interrupted executions require reconciliation and are never automatically repeated.
- Reviewer names are trusted demo inputs, not authenticated identities.

## UI integration

Use the OpenAPI document at `/openapi.json` to generate TypeScript types. The capability response lists supported ingestion formats and whether embeddings are handled by Hindsight or unavailable in the local backend.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/memory/uploads -F "file=@data/remediation_history.json;type=application/json"
curl.exe "http://127.0.0.1:8000/api/memory/failed-remediations?q=retry%20failed&limit=5"
```

All workflow actions and observations returned by these endpoints are simulated.
