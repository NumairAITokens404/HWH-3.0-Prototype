<div align="center">

# Adaptive Incident Intelligence

### Remember failed fixes. Recommend proven actions. Verify recovery.

An evidence-backed incident response platform that learns from operational history,
guards every automated action, and proves that recovery actually happened.

<img src="docs/assets/adaptive-incident-intelligence-banner.png" alt="Adaptive Incident Intelligence control room" width="100%" />

<br />

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-TypeScript-149ECA?style=for-the-badge&logo=react&logoColor=white)](https://react.dev/)
[![Hindsight](https://img.shields.io/badge/Hindsight-Memory-7C3AED?style=for-the-badge)](https://github.com/vectorize-io/hindsight)
[![Ollama](https://img.shields.io/badge/Ollama-Local_AI-111827?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.com/)

[Quick start](#quick-start) · [How it works](#how-it-works) · [Safety model](#safety-model) · [Demo](#demo-walkthrough) · [Docs](#documentation)

</div>

---

## Why this exists

During an incident, the answer is often already somewhere in the organization: a log, a ticket, a failed attempt, or a fix that worked six months ago. The problem is that this evidence is fragmented, hard to search, and easy to forget under pressure.

Adaptive Incident Intelligence turns that history into operational memory. It retrieves relevant incidents, proposes a grounded action, enforces deterministic safety rules, replays the failed operation, and stores the observed result for the next incident.

> **The model can recommend an action. It cannot authorize one.** Python owns citation validation, risk classification, approvals, execution, and recovery verification.

## What it delivers

| | Capability | Responder value |
| :--: | --- | --- |
| 🧠 | **Failure-aware memory** | Successful, partial, and failed fixes remain searchable, preventing repeated mistakes. |
| 🔎 | **Evidence-backed investigation** | Every recommendation is tied to retrieved incident history and ordered outcomes. |
| 🛡️ | **Deterministic safety policy** | Low-risk actions can be automated; sensitive actions stop for named human approval. |
| ✅ | **Independent recovery proof** | A tool saying “success” is not enough; service health and the original operation are checked separately. |
| 📈 | **Measured learning** | Held-out cases are rerun as evidence accumulates, revealing whether the system actually improves. |
| 🔒 | **Local-first operation** | Ollama, SQLite, and simulated connectors support a private, no-paid-API prototype. |

## How it works

<p align="center">
  <img src="docs/assets/system-architecture-v3.png" alt="System architecture from evidence ingestion through verified recovery" width="94%" />
</p>

1. **Ingest** incident records, logs, remediation attempts, and verified outcomes.
2. **Recall** semantically similar cases from Hindsight memory.
3. **Investigate** with deterministic retrieval plus optional local LLM synthesis.
4. **Validate** the proposal schema, citations, action type, and risk in Python.
5. **Approve or execute** according to incident severity and action risk.
6. **Reprocess** the original failed operation after remediation.
7. **Verify** service health and operation recovery independently.
8. **Learn** by writing the observed outcome back to memory.

### The learning loop

<p align="center">
  <img src="docs/assets/learning-loop.svg" alt="Five-step learning loop from evidence to measured improvement" width="88%" />
</p>

The dashboard makes this loop visible. Evidence uploads create memory checkpoints, completed workflows create outcome checkpoints, and the same 12 held-out cases are evaluated at each stage. Workflow clicks never award points; measurements come from live recall and deterministic recovery validation.

## Safety model

Incident severity and action risk are separate decisions:

| Incident severity | Low-risk action | Medium-risk action | High-risk action |
| :-- | :--: | :--: | :--: |
| **Low / Medium** | Auto-execute | Human approval | Human approval |
| **High / Critical** | Human approval | Human approval | Human approval |

Additional guardrails:

- LLM output must match the proposal schema and cite retrieved evidence.
- Unsupported or malformed proposals cannot reach an action tool.
- Approvals are bound to a reviewer identity and durable workflow state.
- Simulation is the default execution backend.
- Connector actions use durable receipts for at-most-once execution.
- Outcomes are recorded as `SUCCESS`, `PARTIAL`, or `FAILED`; observations alone never become successful recovery evidence.

## Product surface

| View | What it shows |
| --- | --- |
| **Overview** | Incident posture, learning progress, memory health, and the guided demo. |
| **Incidents** | Active failures, severity, evidence coverage, and workflow state. |
| **Incident detail** | Retrieved history, avoided failed fixes, proposed action, citations, and recovery proof. |
| **Approvals** | Human decisions for sensitive actions with reviewer-bound authorization. |
| **Memory Explorer** | Uploaded evidence, unresolved observations, failed remediations, and verified outcomes. |
| **Evaluation** | Accuracy, coverage, retrieval precision, failed-fix avoidance, and per-case evidence. |

## Quick start

### Prerequisites

- Python 3.10+
- Node.js 20+ and npm
- Optional: [Ollama](https://ollama.com/) with `qwen3.5:9b`
- Optional: a running Hindsight service for the primary memory integration

### 1. Configure and start the API

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

For the simplest Docker-free run, set these values in `.env`:

```dotenv
MEMORY_BACKEND=sqlite
LLM_PROVIDER=none
```

Then start the API:

```bash
.venv/bin/python -m uvicorn api.app:create_app --factory --reload --port 8000
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)<br />
Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 2. Start the dashboard

In a second terminal:

```bash
cd frontend
cp -n .env.example .env
npm install
npm run dev
```

Open **[http://127.0.0.1:5173](http://127.0.0.1:5173)**.

<details>
<summary><strong>Windows PowerShell commands</strong></summary>

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --reload --port 8000
```

In a second PowerShell window:

```powershell
Set-Location frontend
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm install
npm run dev
```

</details>

### Enable local AI

Set `LLM_PROVIDER=ollama` in `.env`, then run:

```bash
ollama pull qwen3.5:9b
ollama serve
.venv/bin/python -m llm.check --generate
```

If port `11434` is already in use, Ollama is probably already running. The deterministic rules engine remains available when Ollama is offline.

### Enable Hindsight memory

Follow the [Hindsight setup guide](docs/hindsight-setup.md), then set:

```dotenv
MEMORY_BACKEND=hindsight
HINDSIGHT_BASE_URL=http://localhost:8888
```

When Hindsight is configured but unavailable, the API reports a degraded state and leaves memory operations disabled until it reconnects.

### Docker

```bash
docker compose up --build
```

## Demo walkthrough

1. Open **Overview** and select **Reset demo**.
2. Select **Load evidence**, then load **Starter incidents**.
3. Open a low-risk incident and run the automatic simulated remediation.
4. Open a critical incident and show the human approval gate.
5. Complete both workflows, then inspect the learning curve in **Evaluation**.
6. Open **Memory Explorer** to show newly stored outcomes and failed-fix evidence.

> All incidents, action tools, service checks, and recovery outcomes in this repository are synthetic or simulated.

## Under the hood

```text
frontend/     React + TypeScript operations dashboard
api/          FastAPI routes, runtime wiring, and API models
agents/       investigation, remediation, reprocessing, and verification
memory/       Hindsight, SQLite, Postgres, retrieval, and memory writing
services/     workflows, ingestion, approvals, and persistence
tools/        policy, simulation, connectors, and action tools
schemas/      validated incident, proposal, workflow, and outcome models
evaluation/   memory comparison, metrics, and dataset audit
data/         synthetic history, held-out cases, and examples
tests/        backend integration, policy, persistence, and safety tests
```

The dataset contains **18 historical incidents**, **54 ordered remediation outcomes**, and **12 held-out cases** across six failure families. The frontend uses React Query and a typed API client; the backend supports Hindsight, SQLite, and Postgres persistence.

## Testing

```bash
# Backend
.venv/bin/python -m unittest discover -s tests -v

# Frontend
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

Useful evaluation commands:

```bash
.venv/bin/python -m evaluation.evaluate_memory --engine ollama --output reports/local-ollama.json
.venv/bin/python -m evaluation.dataset_audit --output reports/dataset-audit.json
```

The dashboard is the authoritative learning comparison. No fixed improvement percentage is claimed because results depend on the uploaded evidence and configured model.

## Deployment

| Layer | Service | Configuration |
| --- | --- | --- |
| Frontend | **Vercel** | Root `vercel.json`; set `VITE_API_BASE_URL` to the API URL. |
| API | **Render** | `render.yaml` + `Dockerfile`; set CORS and persistence variables. |
| Persistence | **Neon Postgres** | Set the pooled URL as `DATABASE_URL` and use `MEMORY_BACKEND=postgres`. |

Keep `VITE_APPROVAL_TOKEN` empty in public browser deployments because Vite embeds `VITE_` variables in client code. Production approval flows require server-side authentication or a trusted proxy.

## Documentation

| Guide | Covers |
| --- | --- |
| [Getting started](docs/getting-started.md) | Installation and first run |
| [Architecture](docs/architecture.md) | Components, data flow, and trust boundaries |
| [HTTP API](docs/api.md) | Endpoint reference |
| [Implementation](docs/implementation.md) | Runtime behavior and design details |
| [Hindsight setup](docs/hindsight-setup.md) | Memory service configuration |
| [Local model setup](docs/local-model.md) | Ollama and GPU configuration |
| [Measured evaluation](docs/phase-6-evaluation.md) | Dataset and learning metrics |
| [Ingestion](docs/phase-7-ingestion.md) | Evidence formats and failed-remediation memory |
| [Workflow persistence](docs/phase-8-workflow-persistence.md) | Durable execution and approvals |
| [Connectors](docs/phase-9-connectors.md) | Sandbox execution and idempotency |
| [Build journal](docs/README.md) | Phase-by-phase project history |

## Prototype scope

This hackathon prototype demonstrates evidence-grounded, safety-gated incident response. Production use would also require organization-specific action policies, authenticated role management, secrets handling, production connectors, observability, and validation against real incident data.

---

<div align="center">

**Built around a simple principle: an incident is not resolved until recovery is verified.**

</div>
