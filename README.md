# Adaptive Incident Intelligence

### Remember what failed. Recommend what worked. Verify recovery.

An incident-response prototype that uses past experience to help engineers investigate failures, choose a fix, and recover failed operations. **Hindsight is the shared-memory integration at the center of the design; the default demo uses a local mock.**

## The problem

A transaction fails. A queue stops processing. A service becomes unavailable.

Engineers must find the cause, decide what to change, and recover the affected work. A similar incident may already have been solved, but its lessons are scattered across tickets, logs, and individual memory. Teams can repeat a failed fix or retry a transaction before addressing the reason it failed.

**Our problem statement: How can each incident help a team resolve the next similar incident with better evidence and fewer repeated mistakes?**

## Our solution

Adaptive Incident Intelligence connects investigation, controlled remediation, and recovery in one learning loop:

- **Recall experience:** find similar incidents, including fixes that failed.
- **Recommend with evidence:** explain the likely cause and suggested action using past outcomes.
- **Control execution:** automatically run allowed low-risk actions; require human approval for higher-risk changes.
- **Recover the work:** retry the affected transaction, request, or job after remediation.
- **Check and remember:** verify recovery and retain successful, failed, and partial outcomes.

The intended users are incident-response engineers and service support teams. The goal is to reduce repeated troubleshooting and make recovery decisions easier to review.

## Architecture

**Working simulated workflow** ? investigation, approval checks, remediation, retries, verification, and memory feedback run locally. The real Hindsight adapter is implemented; live service verification and LLM reasoning remain pending.

```text
Incident / Failure
        |
        v
Incident Investigator <----> Hindsight Memory
        |                    Past incidents, failed fixes,
        |                    successful fixes, and outcomes
        v
Historical Similarity & Remediation Analysis
        |
        v
Recommended Action + Supporting Evidence
        |
        v
Action Decision Layer
        |
        +-- Allowed low-risk action ------------------+
        |                                             |
        +-- Medium / high risk --> Human approval ----+
                                   |                  |
                              If declined: stop       v
                                             Auto Remediation Agent
                                                      |
                                            Remediation succeeds
                                                      |
                                                      v
                                             Reprocessing Agent
                                                      |
                                                      v
                                             Outcome Verification
                                                      |
                                          Resolved / Failed / Partial
                                                      |
                                                      v
                                             Hindsight Memory Update
                                                      |
                                          Evidence for future incidents
```

If remediation fails, its outcome is captured without starting reprocessing. Approval permits an action; verification determines whether recovery actually worked.

| Role | Plain-language responsibility |
| --- | --- |
| **Incident Investigator** | Understand the failure, compare past responses, and recommend a fix. |
| **Auto Remediation Agent** | Carry out actions allowed by the decision layer. |
| **Reprocessing Agent** | Retry the failed operation after remediation. |
| **Outcome Verification** | Check whether the issue and affected operation recovered. |
| **Hindsight Memory** | Preserve what happened, what was tried, and what worked or failed. |

## A concrete example

A customer transaction fails because of an inconsistent PIN state. Historical incidents contain this sequence:

| Attempt | Recorded result | Lesson |
| --- | --- | --- |
| Retry the transaction | Failed | Retrying alone did not address the problem. |
| Reset the simulated PIN state | Succeeded | Address the state inconsistency first. |
| Retry the transaction again | Succeeded | The order of actions matters. |

**The current demo recommends the PIN-state reset and cites the matching incidents.** It then applies the action policy, performs the simulated fix, retries the transaction, verifies simulated recovery, and stores the outcome. A second incident retrieves the first incident?s experience. A separate high-risk case pauses for approval.

## What makes this approach useful

- **Failed fixes remain useful evidence.** The system retains what to avoid repeating, alongside successful responses.
- **Action order is preserved.** A retry before remediation and a retry after remediation are treated in context.
- **Recommendations are reviewable.** Engineers can inspect the historical incidents behind a suggestion.
- **Uncertainty is visible.** The current investigator declines to recommend when evidence is missing or conflicting.
- **Recovery closes the loop.** The target design checks the affected operation and feeds the observed result back into memory.

## What works today

The working prototype runs the complete recovery loop against an isolated simulator. It includes:

- **18 synthetic historical incidents**, **6 held-out cases**, and **54 recorded action outcomes** across six incident families.
- A mock memory interface and a rule-based investigation baseline.
- An explicit action policy, approval checks, simulated remediation and retries, independent simulated health checks, and outcome storage.
- Tests for evidence handling, recommendations, conflicting history, and data integrity: **50 tests passed in the latest full run**.

**Next:** configure and verify the real Hindsight service, add LLM reasoning, and measure results. The optional Hindsight adapter is implemented and tested offline. Approvals are trusted local inputs; production authentication and durable workflow execution are outside this prototype. Every action and health check is simulated. Mock memory resets on exit; the real backend is designed to retain source records in Hindsight. Recovery-time savings and production accuracy have not yet been measured.

## Try the prototype

Follow the [setup and demo instructions](docs/getting-started.md). Once dependencies are installed, run:

```bash
python main.py
```

The output shows two simulated recoveries, evidence recalled from the first incident, and a high-risk action paused for approval. Structured investigation and workflow results are available through the Python service API. All demo data is synthetic. Default mock mode needs no production connection or API key. [Real Hindsight setup](docs/hindsight-setup.md) is optional and requires a configured service.

## How we will measure success

Compare recommendations **with and without incident memory** on held-out cases: correct fixes, repeated failed actions, troubleshooting steps, root-cause accuracy, and retrieval relevance. These measurements will test whether remembered experience improves decisions.

[Architecture details](docs/architecture.md) ? [Build phases](docs/roadmap.md) ? [Technical documentation](docs/README.md)
