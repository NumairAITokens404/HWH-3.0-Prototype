# Architecture and component boundaries

[Documentation index](README.md) | [Project overview](../README.md)

## Target flow

1. An incident arrives with service, symptoms, error, environment, and operation context.
2. The Incident Investigator consults Hindsight memory and historical similarity/remediation analysis.
3. It returns a likely cause, recommended action, evidence, and confidence assessment.
4. The Action Decision Layer checks an explicit action policy.
5. The Auto Remediation Agent executes an allowed low-risk action, or waits for human approval for a medium/high-risk action. Rejected actions stop here.
6. After successful remediation, the Reprocessing Agent retries the failed transaction, request, or job.
7. Outcome Verification checks whether the underlying problem and failed operation recovered.
8. Resolved, failed, and partial outcomes are written to Hindsight for later investigations.

Human approval authorizes a remediation; it does not itself fix the incident. Approved actions still need execution before reprocessing. This makes the approval branch in the supplied architecture explicit.

## Roles and current implementation

| Architecture role | Code location | Status |
| --- | --- | --- |
| Incident Investigator | `agents/incident_investigator.py` | Deterministic baseline implemented |
| Historical similarity and remediation analysis | `agents/remediation_memory.py`, `memory/memory_retriever.py` | Implemented against mock memory |
| Hindsight memory | `memory/hindsight_client.py`, `memory/memory_writer.py` | Protocol and local mock; real integration planned |
| Action Decision Layer | `tools/risk_classifier.py` | Implemented simulation allowlist and bound approvals |
| Auto Remediation Agent | `agents/auto_remediation.py`, remediation service/tools | Implemented for local simulation |
| Reprocessing Agent | `agents/reprocessing.py`, `tools/reprocessing_tools.py` | Implemented with remediation prerequisite |
| Outcome Verification | `agents/outcome_verifier.py`, `services/verification_service.py` | Independent simulated health and operation checks |
| Memory update | Outcome storage contract in `memory/hindsight_client.py` | Verified simulated outcomes written by `IncidentWorkflow` |

The Remediation Memory module supports the investigator. It is distinct from the Auto Remediation Agent, which executes approved actions.

## Design principles

- **Preserve order:** an action can fail before a fix and succeed afterward.
- **Keep evidence:** recommendations retain incident IDs and complete action histories.
- **Allow uncertainty:** return insufficient evidence when comparable history cannot support a recommendation.
- **Separate recommendation and authorization:** every current investigation result has `execution_authorized: false`.
- **Verify recovery:** a successful tool response alone is not proof that the failed operation recovered.
- **Retain every outcome:** future memory should contain failures and partial recoveries as well as successful fixes.

The hackathon's action tools are simulated. PIN reset is labeled low risk only within the synthetic demo; it is not a production authorization policy.

## Simulation and execution boundaries

`tools/simulation.py` owns explicit scenario state. It models tool acknowledgements separately from service health and operation recovery, so acknowledgements cannot establish success by themselves. The workflow returns SUCCESS when both checks pass, PARTIAL when only one passes, and FAILED when neither passes. Failed remediation skips reprocessing.

`Outcome.tool_result` retains tool acknowledgements while `Outcome.result` retains the observed step outcome. `IncidentMemory.final_outcome` records overall recovery. Thus a failed retry can remain FAILED in action history while overall recovery is PARTIAL because the service itself recovered. Root causes written from investigations remain historical hypotheses, not independently established causes.

Approval identities are trusted local inputs. The simulator is a test fixture, not a security boundary or production connector. Workflow state and duplicate protection are in-process, synchronous, and not durable across restarts.
