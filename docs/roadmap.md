# Remaining implementation phases

[Documentation index](README.md)

Phases 1?4 now provide the complete local simulation: investigation, policy checks, remediation, retries, verification, and memory feedback. See [Phase 3](phase-3-actions.md) and [Phase 4](phase-4-recovery.md) for the completed work. The following integrations and evaluation remain planned.

## Phase 5: real Hindsight and configurable LLM reasoning

1. Adapter implemented against the official SDK. Configure a service and complete the [live persistence check](hindsight-setup.md).
2. Add one configurable LLM client for interpretation and recommendation synthesis.
3. Validate structured responses against the existing contracts and retain evidence references.
4. Keep arithmetic, risk authorization, and execution checks in deterministic Python.
5. Test missing credentials, unavailable services, invalid output, and insufficient evidence.

**Completion check:** the real services can replace the offline baseline without bypassing validation or approval rules.

## Phase 6: evaluation and demonstration

1. Compare recommendations with and without memory on held-out incidents.
2. Calculate correct remediation, repeated failed-action rate, troubleshooting steps, root-cause accuracy, and retrieval relevance.
3. Include unfamiliar and conflicting cases, not only repeats of fixture patterns.
4. Report measured results with dataset size and limitations.
5. Extend the existing simulated loop demonstration with measured comparisons and real memory integration.

**Completion check:** every performance claim is backed by a reproducible measurement. No recovery-time savings or production accuracy is claimed before evaluation.
