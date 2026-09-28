# HTTP API for the web platform

[Documentation index](README.md)

The FastAPI layer exposes the existing investigation and simulated workflow services without moving policy into the browser. OpenAPI is the source of truth for generated frontend types.

The React frontend selects the live adapter when `frontend/.env` contains `VITE_API_MODE=http`. Its dashboard routes use the `/api/ui/*` facade below; core automation remains in the same runtime and policy services used by the CLI and typed API.

The UI facade starts with an empty session projection. Uploading history populates the incident queue, memory explorer, and current evaluation result. `POST /api/ui/reset` clears this projection and its simulated UI workflows without deleting durable backend records.

## Start locally

```powershell
.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API schema. Configure allowed frontend origins with `API_CORS_ORIGINS`.

The root URL `http://127.0.0.1:8000/` returns a small service status response. Use `/api/health` for the health contract and `/docs` for interactive API testing.

`GET /api/health` and `GET /api/capabilities` report `action_backend` and whether actions are simulated. The safe default is `simulation`; see [sandbox connectors](phase-9-connectors.md) before enabling connector execution.

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
| `GET /api/ui/overview` | Supply live dashboard counters and recent incidents. |
| `GET /api/ui/incidents` | List the held-out demonstration incidents and their workflow states. |
| `GET /api/ui/incidents/{incident_id}` | Return live investigation and workflow state for one incident. |
| `POST /api/ui/incidents/{incident_id}/workflow` | Run or resume the server-owned demonstration case. |
| `POST /api/ui/incidents/{incident_id}/approval` | Submit the bound UI approval decision. |
| `GET /api/ui/memory` | Search complete memory records for the memory explorer. |
| `GET /api/ui/evaluation` | Run and return the deterministic checkpoint comparison. |
| `POST /api/ui/reset` | Reset the dashboard learning demonstration. |

The API generates demo incident IDs. The browser never submits `required_action`, health truth, or expected evaluation labels. Low-risk scenarios finish immediately. High-risk scenarios return `HUMAN_APPROVAL_REQUIRED` and a `decision.request_id` that must be returned with the reviewer decision.

## Approval lifecycle

- A mismatched request ID returns `BLOCKED`; the correct request may still be submitted.
- A bound rejection returns `DENIED` and permanently closes the run.
- A successful or denied run is removed from the active registry while its checkpoint and audit history remain durable.
- Pending approvals survive API restarts through `WORKFLOW_DB_PATH`; the original investigation is restored without another model call.
- An approved action is checkpointed as `EXECUTING` before it runs. Ambiguous interrupted executions require reconciliation and are never automatically repeated.
- With no approval credentials configured, reviewer names remain trusted local demo inputs.
- To authenticate reviewers, set `APPROVAL_IDENTITIES_JSON` to a JSON object such as `{"alice":"a-long-random-token"}`. Send that token as `Authorization: Bearer ...`; the server derives and audits `alice` and rejects a conflicting body reviewer.
- Store real tokens only in `.env` or deployment secrets. Do not commit them.

## UI integration

Use the OpenAPI document at `/openapi.json` to generate TypeScript types. The capability response lists supported ingestion formats and whether embeddings are handled by Hindsight or unavailable in the local backend.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/memory/uploads -F "file=@data/remediation_history.json;type=application/json"
curl.exe "http://127.0.0.1:8000/api/memory/failed-remediations?q=retry%20failed&limit=5"
```

All workflow actions and observations returned by these endpoints are simulated.
