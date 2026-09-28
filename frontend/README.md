# Adaptive Incident Intelligence frontend

Responsive React operations console for the incident memory, investigation, approval, simulated remediation, verification, and evaluation workflow.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env`, start the Python API on port 8000, and open the URL printed by Vite. `VITE_API_MODE=http` connects the console to FastAPI. Set it to `mock` for a fixture-only UI demonstration.

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
- `/memory/upload` - JSON upload and processing pipeline
- `/approvals` - medium and high risk review queue
- `/evaluation` - synthetic before and after memory comparison

## API boundary

Pages use the `IncidentApi` interface in `src/api/client.ts`. `src/api/httpApi.ts` maps it to FastAPI, while `src/api/mockApi.ts` remains available for an offline UI demonstration.

Live integration points:

- `POST /api/memory/uploads`
- `GET /api/ui/memory`
- `POST /api/incidents/investigate`
- `GET /api/ui/incidents`
- `GET /api/ui/incidents/:incidentId`
- `POST /api/ui/incidents/:incidentId/workflow`
- `POST /api/ui/incidents/:incidentId/approval`
- `GET /api/ui/overview`
- `GET /api/ui/evaluation`

All remediation actions and observations shown by the frontend remain explicitly simulated. Uploads use the configured memory backend; Hindsight performs embeddings when that backend is active.

## Design system

The interface uses a restrained operations palette: navy navigation, blue actions, purple Hindsight evidence, green verified outcomes, amber approval states, and red failures. Surfaces use one-pixel borders, small radii, limited shadow, and compact 8px-based spacing. Hover behavior is limited to color changes and disclosure state transitions.

Status is always communicated with text in addition to color. Incident IDs, error codes, action names, evidence IDs, and chunk references use monospace type; all other interface text uses the system sans-serif stack.
