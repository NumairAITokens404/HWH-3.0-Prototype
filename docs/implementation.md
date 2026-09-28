# Implementation reference

[Documentation index](README.md)

## File guide: purpose and logic

| File(s) | Function and reason |
| --- | --- |
| `schemas/incident.py` | Validate incident inputs; keep evaluation answers separate from the input given to the investigator. |
| `schemas/remediation.py` | Define action, risk, and bounded confidence fields so recommendations have a consistent shape. |
| `schemas/outcome.py` | Preserve ordered attempts, root causes, and results; retry success depends on what happened before it. |
| `schemas/investigation.py` | **New:** typed evidence, action counts, and recommendation/abstention output for backend consumers. |
| `memory/hindsight_client.py` | Isolate the memory contract from its provider; the mock uses lexical similarity and stores both failed and successful attempts. |
| `memory/memory_writer.py` | Validate fixture relationships and seed historical records without leaking held-out answers. |
| `memory/memory_retriever.py` | Give callers one small retrieval entry point that retains complete histories. |
| `agents/remediation_memory.py` | **Implemented:** filter comparable incidents and count verified success/failure/partial results separately from unverified attempts. |
| `agents/incident_investigator.py` | **Implemented:** identify fixes followed by successful retries, cite evidence, and abstain when support is missing or conflicting. |
| `services/incident_service.py` | **Implemented:** compose memory analysis and investigation into one backend-callable function. |
| `main.py` | **Updated:** validate/seed data and print the investigation result as JSON. |
| `config.py`, `.env.example` | Configure the data directory through the environment; no credentials required. |
| `data/incidents.json` | Historical incident inputs across six recurring problem families. |
| `data/remediation_history.json` | Root causes and ordered failed/successful attempts for those incidents. |
| `data/test_incidents.json` | Held-out inputs and expected answers for tests; labels are not passed to the investigator. |
| `tests/test_phase_one.py` | Check schema, dataset, retrieval, and memory-write behavior. |
| `tests/test_investigation.py` | **New:** check recommendations, contradictory evidence, abstention, risk preservation, and absence of writes/execution. |
| `agents/outcome_verifier.py`, `services/verification_service.py` | Placeholders for explicit recovery checks. |
| `tools/incident_tools.py` | Placeholder for incident inspection helpers. |
| `tools/risk_classifier.py` | Placeholder for deterministic authorization rules, independent of model suggestions. |
| `tools/remediation_tools.py`, `services/remediation_service.py` | Placeholders for allowed simulated remediation and orchestration. |
| `tools/reprocessing_tools.py` | Placeholder for retrying operations after remediation. |
| `evaluation/evaluate_memory.py`, `evaluation/metrics.py` | Placeholders for measured comparisons with/without memory. |
| `requirements.txt`, `.gitignore`, package `__init__.py` files | Dependencies, ignored local artifacts, and Python package boundaries. |
| `README.md` | Current implementation, architecture, run instructions, and next steps. |

## Project structure

The repository root is the application root; no nested checkout or application directory is needed.

```text
agents/
    incident_investigator.py       # Deterministic investigation baseline
    remediation_memory.py         # Historical evidence analysis
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
services/
    incident_service.py           # Investigation entry point
    remediation_service.py        # Placeholder
    verification_service.py       # Placeholder
schemas/
    incident.py                   # Incident and held-out evaluation case
    remediation.py                # RemediationAction and risk level
    investigation.py              # Evidence and investigation result
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
    test_investigation.py
config.py
main.py
requirements.txt
.env.example
README.md
```

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
