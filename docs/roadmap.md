# Remaining implementation phases

[Documentation index](README.md)

Phases 1 and 2 establish data contracts and a deterministic investigation baseline. The steps below are planned, not implemented.

## Phase 3: action decision and simulated remediation

1. Define an explicit allowlist of supported actions and their risk levels.
2. Allow automatic execution only for predefined low-risk simulated actions.
3. Return `HUMAN_APPROVAL_REQUIRED` for medium/high risk; prevent unapproved execution.
4. Add the Auto Remediation Agent's orchestration over simulated tools.
5. Test unknown actions, denied approval, failed execution, and approved execution.

**Completion check:** a recommendation can reach a simulated action only through the decision layer. Model output and historical risk labels cannot bypass that gate.

## Phase 4: reprocessing, verification, and outcome capture

1. Add the Reprocessing Agent's retry flow after successful remediation.
2. Verify operation recovery independently of the remediation tool's success response.
3. Distinguish `SUCCESS`, `FAILED`, and `PARTIAL` outcomes.
4. Store the actual action sequence, risk, verification result, and lesson in memory.
5. Demonstrate a later incident retrieving the newly stored experience.

**Completion check:** failed/partial recovery is retained alongside success, and an approved high-risk action passes through remediation before retrying the operation.

## Phase 5: real Hindsight and configurable LLM reasoning

1. Verify the actual Hindsight SDK/API and implement an adapter behind `HindsightClient`.
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
5. Demonstrate the full incident-to-verified-outcome loop with simulated actions.

**Completion check:** every performance claim is backed by a reproducible measurement. No recovery-time savings or production accuracy is claimed before evaluation.
