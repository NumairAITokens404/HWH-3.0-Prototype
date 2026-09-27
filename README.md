# Adaptive Incident Intelligence

Incident intelligence, simulated remediation, and reprocessing with shared incident memory.

## Status: Phase 1

Phase 1 implements the Python project structure, Pydantic schemas, synthetic datasets, and a local mock Hindsight interface. Run `main.py` to validate the fixtures and exercise memory retrieval and outcome write-back.

Agents, LLM integration, risk classification, action execution, reprocessing, outcome verification, and performance evaluation are reserved for later phases. Their modules are explicit placeholders. There is no frontend or production integration.

## Target architecture

The planned workflow is:

```text
Incident / failure
  -> Incident Investigator
  -> Hindsight memory: similar incidents + failed/successful actions
  -> Recommended action
  -> Risk classification
       LOW: simulated automatic execution
       MEDIUM / HIGH: human approval required
  -> Reprocessing
  -> Outcome verification: SUCCESS / FAILED / PARTIAL
  -> Hindsight outcome update
```

| Planned component | Responsibility |
| --- | --- |
| Incident Investigator | Interpret the incident and synthesize a structured recommendation with evidence and confidence. Does not execute actions itself. |
| Remediation Memory | Retrieve relevant incidents, root causes, successful fixes, and actions that previously failed. |
| Outcome Verifier | Check whether remediation and reprocessing actually recovered the operation. |
| Action decision layer | Classify actions and require approval for medium/high risk actions before execution. |
| Remediation and reprocessing tools | Simulate allowed actions and retries for the hackathon. |
| Hindsight memory adapter | Retain experiences so later investigations can retrieve their context and outcomes. |

PIN reset is a synthetic low-risk action in the sample dataset only. These labels do not authorize real security-sensitive operations. No actions are executed in Phase 1.

## Project structure

The repository root is the application root; no nested checkout or application directory is needed.

```text
agents/
    incident_investigator.py       # Placeholder
    remediation_memory.py         # Placeholder
    outcome_verifier.py            # Placeholder
memory/
    hindsight_client.py           # Protocol + in-memory mock
    memory_writer.py              # Dataset validation and historical seeding
    memory_retriever.py            # Retrieval facade
tools/                           # All modules are placeholders
    incident_tools.py
    remediation_tools.py
    reprocessing_tools.py
    risk_classifier.py
services/                         # All modules are placeholders
    incident_service.py
    remediation_service.py
    verification_service.py
schemas/
    incident.py                   # Incident and held-out evaluation case
    remediation.py                # RemediationAction and risk level
    outcome.py                    # Outcome and IncidentMemory
data/
    incidents.json
    remediation_history.json
    test_incidents.json
evaluation/                      # Placeholder modules; no performance claims
    evaluate_memory.py
    metrics.py
tests/
    test_phase_one.py
config.py
main.py
requirements.txt
.env.example
README.md
```

## Setup and run

Use Python 3.10 or newer. Tested locally with Python 3.13 and Pydantic 2.13.5. Install dependencies once; the demo then runs offline without API keys.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
.venv/bin/python -m unittest discover -s tests -v
```

If virtual-environment creation cannot bootstrap pip but creates its Python executable, an existing system pip can install the dependencies with:

```powershell
python -m pip --python .venv\Scripts\python.exe install -r requirements.txt
```

Configuration comes from `INCIDENT_DATA_DIR`, which defaults to the `data/` directory beside `config.py`. Relative overrides resolve against the current working directory. `.env.example` documents the variable; Phase 1 does not automatically load `.env` files.

## Data contracts

- **Incident:** ID, service, severity, symptoms, environment, and optional error details, customer/transaction/job IDs, and recent change.
- **RemediationAction:** action name, description, risk level (`LOW`, `MEDIUM`, `HIGH`), reason, and confidence between 0 and 1.
- **Outcome:** unique outcome ID within an incident, incident ID, action, result (`SUCCESS`, `FAILED`, `PARTIAL`), optional reprocessing result, lesson, risk level, verification flag, and optional resolution time.
- **IncidentMemory:** incident, optional root cause and recommendation, ordered outcomes, and optional final resolution.
- **EvaluationCase:** held-out incident plus expected root cause, recommended action, relevant historical IDs, and actions to avoid before remediation. Labels are kept outside the incident input.

Schemas reject unknown fields, empty required strings, invalid enum values, mismatched outcome incident IDs, duplicate outcome IDs within a record, and invalid confidence or duration values.

## Synthetic dataset

There are **18 historical incidents and 6 held-out cases**, spanning:

1. Customer PIN / master-data inconsistency.
2. Payment provider routing failure.
3. Database connection exhaustion.
4. Queue processing failure.
5. Catalog cache inconsistency.
6. Downstream service timeout.

Each family has three historical incidents and one held-out case. Historical records contain an initial failed retry, a successful remediation, and a successful retry after remediation: **54 ordered action outcomes** in total. All incidents, identifiers, outcomes, and durations are synthetic fixtures, not observed production results.

`incidents.json` contains historical inputs. `remediation_history.json` pairs those inputs with root causes, actions, and resolutions. `test_incidents.json` contains evaluation inputs and labels and is never passed to historical seeding. The loader checks matching IDs/content, valid references, and separation between history and held-out inputs.

## Mock Hindsight interface

`HindsightClient` is an application-owned Python protocol with five operations:

- `store_incident_memory(memory)`
- `retrieve_similar_incidents(incident, limit=5)`
- `store_remediation_outcome(outcome)`
- `retrieve_failed_actions(incident_id)`
- `retrieve_successful_actions(incident_id)`

`MockHindsightClient` implements this contract locally. These names are not claims about methods in the real Hindsight SDK. The adapter file marks the future integration point explicitly.

Retrieval ranks records using service match (0.4), error-code match (0.3), symptom-token Jaccard overlap (0.2), and environment match (0.1). Environment alone cannot produce a match. Results exclude the query's own ID, break ties by incident ID, and include complete histories, including failed and partial outcomes. The similarity score is a deterministic mock ranking score, not calibrated confidence or semantic relevance.

Identical writes are idempotent. Conflicting incident or outcome IDs raise an error instead of silently overwriting history. Outcome writes require an existing incident. Returned records are defensive copies. Memory lasts for one client instance; nothing is persisted across process restarts or written back to the fixture files.

### Phase 1 demonstration

Running `main.py` validates all three datasets, seeds only historical records, and queries the held-out customer PIN incident. Its output includes:

```text
Phase 1: validated 18 historical incidents and 6 held-out cases.
Mock retrieval for TEST-001 (customer-service):
  INC-101: similarity=1.000
    reprocess_transaction: FAILED ...
    reset_customer_pin: SUCCESS ...
    reprocess_transaction: SUCCESS ...
```

The demo then stores a clearly marked synthetic failed outcome and reads it back. This exercises the memory contract; it does not recommend or execute a remediation, verify recovery, or demonstrate measured agent improvement.

## Verification and later evaluation

The Phase 1 tests cover schema constraints, dataset integrity, held-out separation, retrieval for all six families, ordered successful/failed actions, outcome write/read, duplicate conflicts, unknown IDs, empty/unrelated queries, deterministic ranking, and copy isolation.

Later evaluation will compare recommendations with and without historical memory, measuring correct remediation, repeated failed actions, troubleshooting steps, root-cause accuracy, and retrieval relevance. The evaluation modules are placeholders, and no final performance numbers are claimed.

## Next phase

Implement the Remediation Memory and Incident Investigator agents against the existing contracts, using a configurable LLM client and structured outputs. Subsequent phases can add deterministic risk classification, simulated remediation, reprocessing, explicit verification, and the full learning loop. Phase 1 stops before this work.
