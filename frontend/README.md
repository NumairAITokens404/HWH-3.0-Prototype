# Adaptive Incident Intelligence frontend

Responsive React operations console for the incident memory, investigation, approval, simulated remediation, verification, and evaluation workflow.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env`, start the Python API on port 8000, and open the URL printed by Vite. The default `VITE_API_MODE=http` connects the console to FastAPI. The fixture adapter exists only for isolated component tests and is not the product demo path.

## Validate

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

## Routes

- `/` - operations overview and demo entry point
- `/incidents` - searchable incident queue
- `/incidents/:id` - investigation, evidence, policy, simulated workflow, and verification
- `/memory` - Hindsight memory explorer with ordered outcomes and source chunks
- `/memory/upload` - persistent session upload queue for JSON, CSV, Markdown, text/log, and PDF evidence
- `/approvals` - medium and high risk review queue
- `/evaluation` - repeated held-out evaluation at each real memory checkpoint

## API boundary

Pages use the `IncidentApi` interface in `src/api/client.ts`. `src/api/httpApi.ts` maps it to FastAPI. `src/api/mockApi.ts` is limited to isolated frontend tests.

Live integration points:

- `POST /api/memory/uploads`
- `GET /api/ui/uploads`
- `DELETE /api/ui/uploads/:uploadId`
- `GET /api/ui/memory`
- `POST /api/incidents/investigate`
- `GET /api/ui/incidents`
- `GET /api/ui/incidents/:incidentId`
- `POST /api/ui/incidents/:incidentId/workflow`
- `POST /api/ui/incidents/:incidentId/approval`
- `GET /api/ui/overview`
- `GET /api/ui/evaluation`

All remediation actions and observations shown by the frontend remain explicitly simulated. Uploads use the configured memory backend; Hindsight performs embeddings when that backend is active.

## Demo lifecycle

The live dashboard begins with an isolated bank on the configured backend. Uploading evidence triggers a full held-out evaluation, and verified outcomes trigger another checkpoint. Accuracy, coverage, retrieval precision, and failed-fix avoidance are recomputed from actual recommendations and recalled IDs. A workflow click never awards progress, and a checkpoint may remain flat or decline. **Reset demo** rotates the dashboard to a new clean bank or database.

## Design system

The interface uses a restrained operations palette: navy navigation, blue actions, purple Hindsight evidence, green verified outcomes, amber approval states, and red failures. Surfaces use one-pixel borders, small radii, limited shadow, and compact 8px-based spacing. Hover behavior is limited to color changes and disclosure state transitions.

Status is always communicated with text in addition to color. Incident IDs, error codes, action names, evidence IDs, and chunk references use monospace type; all other interface text uses the system sans-serif stack.
