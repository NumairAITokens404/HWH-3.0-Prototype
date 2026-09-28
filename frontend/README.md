# Adaptive Incident Intelligence frontend

Responsive React operations console for the incident memory, investigation, approval, simulated remediation, verification, and evaluation workflow.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite. The application currently uses a typed mock adapter and transforms the repository fixtures in `../data/` into UI responses.

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

Pages use the `IncidentApi` interface in `src/api/client.ts`. `src/api/mockApi.ts` supplies fixture-backed behavior. `src/api/httpApi.ts` documents the planned HTTP endpoint mapping. Switch the exported adapter in `src/api/index.ts` after those endpoints exist.

Planned integration points:

- `POST /api/memory/uploads`
- `GET /api/memory/uploads/:jobId`
- `GET /api/memory/search`
- `POST /api/incidents/investigate`
- `POST /api/workflows`
- `POST /api/workflows/:incidentId/approval`
- `GET /api/evaluation/summary`

All remediation actions and observations shown by the current frontend are explicitly simulated. Hindsight storage and embedding stages are represented by the mock adapter until the corresponding backend endpoints are available.

## Design system

The interface uses a restrained operations palette: navy navigation, blue actions, purple Hindsight evidence, green verified outcomes, amber approval states, and red failures. Surfaces use one-pixel borders, small radii, limited shadow, and compact 8px-based spacing. Hover behavior is limited to color changes and disclosure state transitions.

Status is always communicated with text in addition to color. Incident IDs, error codes, action names, evidence IDs, and chunk references use monospace type; all other interface text uses the system sans-serif stack.
