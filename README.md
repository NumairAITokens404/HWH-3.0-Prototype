# Adaptive Incident Intelligence

### Remember failed fixes. Recommend proven actions. Verify recovery.

Incident responders often repeat work because the useful parts of earlier incidents are scattered across logs, tickets, and individual memory. A retry may even be repeated before anyone fixes the condition that caused it to fail.

Adaptive Incident Intelligence turns every incident into reusable evidence. It retrieves similar cases, uses a local LLM to explain the strongest historical recovery sequence, applies a deterministic risk policy, simulates the approved action, retries the failed operation, verifies recovery, and stores the observed result.

## Why this matters

For an on-call engineer, the system answers four practical questions:

1. **Have we seen this failure before?**
2. **What worked, and what already failed?**
3. **Can this action run automatically, or does a person need to approve it?**
4. **Did the service and the affected operation actually recover?**

The system preserves failed and partial outcomes as evidence. A successful tool response alone never counts as recovery.

## End-to-end flow

```text
Incident
   |
   v
Retrieve similar incidents and ordered outcomes
   |
   v
Local LLM proposal (Qwen3.5 9B) + evidence citations
   |
   v
Python validation: supported action, real citations, fixed risk policy
   |
   +-- low risk --------------------> simulated remediation
   |
   +-- medium/high risk --> human approval --> simulated remediation
                                              |
                                              v
                                      reprocess failed work
                                              |
                                              v
                                  verify service + operation recovery
                                              |
                                              v
                                  store success / failure / partial result
```

The LLM proposes and explains. Python owns citation checks, action support, risk classification, approval binding, and execution. Unsupported model output cannot reach an action tool.

## Working prototype

- **Local reasoning:** Ollama with `qwen3.5:9b`, selected for the project machine's RTX 5070 Ti 12 GB GPU. The measured run used an 8,192-token context and loaded fully on the GPU.
- **Persistent memory without Docker:** SQLite stores incidents and outcomes across runs.
- **Hindsight-ready:** the official SDK adapter, backend selection, and offline contract tests are implemented. A live Hindsight service remains optional.
- **History ingestion:** validated JSON, CSV, Markdown, logs, and text-based PDFs preserve complete records and create searchable failed-remediation chunks; Hindsight handles embeddings when configured.
- **Durable control plane:** pending approvals and audit events persist in SQLite, including a pre-execution checkpoint that prevents automatic duplicate actions after an interrupted run.
- **Complete simulated loop:** investigation, policy checks, human approval pause/resume, remediation, retry, independent verification, and memory feedback.
- **Structured and guarded:** Pydantic validates every input and model proposal; malformed, truncated, unsupported, or uncited output is rejected or disclosed as fallback.
- **Synthetic benchmark:** 18 historical incidents, 54 ordered outcomes, and 6 held-out cases across six failure families.

## Measured result

On the six synthetic held-out cases, using `qwen3.5:9b` locally:

| Evaluation | Raw action accuracy | Accepted action accuracy | Accepted coverage | Failed actions repeated | Model fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Without incident memory | 1/6 | 0/6 | 0/6 | 0 | 0 |
| With incident memory | 6/6 | 6/6 | 6/6 | 0 | 0 |

All three additional challenges—unknown error, missing error, and conflicting history—returned **insufficient evidence** and executed nothing.

These are small synthetic fixtures that resemble the stored incident families. They demonstrate the workflow and safety gates; they do not establish production accuracy or recovery-time savings. Four memory-backed cases paused for approval, while two low-risk cases completed simulated recovery.

## Example

A transaction fails with an invalid PIN state. Similar incidents show this order:

| Step | Outcome |
| --- | --- |
| Retry transaction immediately | Failed |
| Reset the stale PIN state | Succeeded |
| Retry after remediation | Succeeded |

The investigator recommends `reset_customer_pin`, cites the supporting incidents or outcomes, and the low-risk demo policy permits simulated execution. It then retries the transaction, verifies both service health and transaction recovery, and stores the observed sequence for later incidents.

## Run it

Requirements: Python 3.10+, Ollama, and the local `qwen3.5:9b` model. No paid API or Docker is required.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen3.5:9b
Copy-Item .env.example .env
```

Set `MEMORY_BACKEND=sqlite` and `LLM_PROVIDER=ollama` in `.env`, then run:

```powershell
.venv\Scripts\python.exe -m llm.check --generate
.venv\Scripts\python.exe main.py
```

Useful commands:

```powershell
# Fast offline rules demo
.venv\Scripts\python.exe main.py --engine rules --memory mock

# Investigate without executing
.venv\Scripts\python.exe main.py investigate --input data/examples/incident.json

# Review a high-risk simulated action
.venv\Scripts\python.exe main.py run --input data/examples/high-risk-scenario.json --memory mock --interactive

# Reproduce the local evaluation
.venv\Scripts\python.exe -m evaluation.evaluate_memory --engine ollama --output reports/local-ollama.json

# Run all tests
.venv\Scripts\python.exe -m unittest discover -s tests -v

# Start the API for the web platform
.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --reload --port 8000

# Upload existing incident history after starting the API
curl.exe -X POST http://127.0.0.1:8000/api/memory/uploads -F "file=@data/remediation_history.json;type=application/json"
```

All actions, service checks, incidents, and outcomes in this repository are simulated or synthetic.

## Documentation

- [Getting started](docs/getting-started.md)
- [Architecture and trust boundaries](docs/architecture.md)
- [Local model and GPU setup](docs/local-model.md)
- [Measured evaluation](docs/phase-6-evaluation.md)
- [HTTP API for the web platform](docs/api.md)
- [File ingestion and failed-remediation memory](docs/phase-7-ingestion.md)
- [Workflow persistence and Docker storage](docs/phase-8-workflow-persistence.md)
- [Implementation reference](docs/implementation.md)
- [Optional Hindsight setup](docs/hindsight-setup.md)
- [Build phases](docs/README.md)
