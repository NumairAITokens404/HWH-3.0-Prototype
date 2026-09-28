# Implementation reference

[Documentation index](README.md)

## File guide

| File(s) | Responsibility |
| --- | --- |
| `agents/incident_investigator.py` | Recommend a historically supported fix or abstain. |
| `agents/remediation_memory.py` | Filter comparable history and count ordered outcomes. |
| `agents/auto_remediation.py` | Call the authorized simulated remediation tool. |
| `agents/reprocessing.py` | Retry the failed operation after remediation. |
| `agents/outcome_verifier.py` | Classify recovery from independent simulated observations. |
| `services/incident_service.py` | Investigation-only API plus the full `IncidentWorkflow`, approval resume, memory capture, and duplicate handling. |
| `services/remediation_service.py` | Sequence remediation and conditional retry. |
| `services/verification_service.py` | Backend entry point for recovery checks. |
| `tools/risk_classifier.py` | Explicit policy and approval binding; suggested risk cannot override policy. |
| `tools/remediation_tools.py` | Recheck permission before mock execution. |
| `tools/reprocessing_tools.py` | Retry entry point with a remediation prerequisite. |
| `tools/simulation.py` | Own explicit scenario truth and mutable local operation state. |
| `tools/incident_tools.py` | Reserved placeholder for future incident inspection helpers. |
| `memory/hindsight_adapter.py`, `memory/factory.py` | Real SDK adapter and explicit backend selection; live verification pending. |
| `memory/check_hindsight.py` | Connection and persistent write/read probe. |
| `tests/test_hindsight_adapter.py` | 12 offline adapter and SDK contract tests. |
| `memory/hindsight_client.py` | Memory protocol and local in-memory implementation. |
| `memory/memory_writer.py` | Validate datasets and seed historical records. |
| `memory/memory_retriever.py` | Small facade that preserves complete histories. |
| `schemas/incident.py` | Incident inputs and separate evaluation labels. |
| `schemas/remediation.py` | Recommendation contract and risk labels. |
| `schemas/outcome.py` | Ordered observed results, tool responses, and memory records. |
| `schemas/investigation.py` | Evidence, counts, recommendation, and abstention output. |
| `schemas/workflow.py` | Approval, simulation, execution, and recovery contracts. |
| `data/*.json` | Historical inputs, remediation histories, and held-out labels. |
| `tests/test_phase_one.py` | Foundation behavior: 11 tests. |
| `tests/test_investigation.py` | Recommendation behavior: 11 tests. |
| `tests/test_workflow.py` | Approval, execution, verification, and memory feedback: 16 tests. |
| `evaluation/evaluate_memory.py`, `evaluation/metrics.py` | Future measured evaluation; placeholders. |
| `config.py`, `.env.example` | Data-directory configuration. |
| `main.py` | Two simulated recoveries and one high-risk approval pause. |
| `requirements.txt`, `.gitignore`, `__init__.py` files | Dependencies, ignored artifacts, and package structure. |
| `README.md`, `docs/` | Project overview and phase/technical documentation. |

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

`HindsightClient` is an application-owned Python protocol with six operations:

- `get_incident_memory(incident_id)`
- `store_incident_memory(memory)`
- `retrieve_similar_incidents(incident, limit=5)`
- `store_remediation_outcome(outcome)`
- `retrieve_failed_actions(incident_id)`
- `retrieve_successful_actions(incident_id)`

`MockHindsightClient` implements this contract locally. These names are not claims about methods in the real Hindsight SDK. The real implementation is in `hindsight_adapter.py`; see the Phase 5A document for its validation status.

Retrieval ranks records using service match (0.4), error-code match (0.3), symptom-token Jaccard overlap (0.2), and environment match (0.1). Environment alone cannot produce a match. Results exclude the query's own ID, break ties by incident ID, and include complete histories, including failed and partial outcomes. The similarity score is a deterministic mock ranking score, not calibrated confidence or semantic relevance.

Identical writes are idempotent. Conflicting incident or outcome IDs raise an error instead of silently overwriting history. Outcome writes require an existing incident. Returned records are defensive copies. Memory lasts for one client instance; nothing is persisted across process restarts or written back to the fixture files.

`Outcome.tool_result` preserves acknowledgements separately from verified results. `IncidentMemory.final_outcome` stores overall SUCCESS/FAILED/PARTIAL recovery. `schemas/workflow.py` adds approval, policy, scenario, tool, verification, and workflow result contracts.
