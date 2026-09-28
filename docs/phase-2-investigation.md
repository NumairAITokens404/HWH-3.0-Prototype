# Phase 2: investigation baseline

[Documentation index](README.md) | [Previous: foundations](phase-1-foundations.md) | [Next: remaining phases](roadmap.md)

**Status: deterministic baseline and guarded local LLM reasoning implemented.** See [Phase 5B](phase-5-llm.md) for the model layer.

## Steps completed

1. Implemented `agents/remediation_memory.py` to select comparable history and count outcomes.
2. Added `schemas/investigation.py` for evidence, action summaries, and structured results.
3. Implemented `agents/incident_investigator.py` to identify historically supported fixes or return insufficient evidence.
4. Connected both modules through `services/incident_service.py`.
5. Updated `main.py` to print the customer PIN investigation as JSON.
6. Added 11 tests covering recommendations, conflicting evidence, and the boundary before execution.

## Investigation logic

The memory module examines the top five retrieved records, then keeps matches with the same service, environment, and nonempty error code and a similarity of at least 0.7. This deliberately narrow baseline can miss relevant cases beyond those five records or cases without an error code.

The investigator looks for a verified successful fix immediately before the final verified successful retry. It counts supporting incidents, not raw attempts. A failed, partial, or unverified attempt at a candidate fix blocks that candidate. Equal support for competing fixes, or missing/conflicting root causes among comparable records, produces `INSUFFICIENT_EVIDENCE`.

Confidence is a heuristic: sum of supporting similarity scores divided by `(supporting incident count + 1)`. It discounts small samples and is not a calibrated probability. Historical sequence is evidence of association, not proof of causality. The highest recorded risk for the chosen action is retained; it is not a fresh authorization decision. Every result has `execution_authorized: false`.

## Verification

At completion of this phase, 22 tests passed: 11 foundation tests and 11 investigation tests. Phase 4 adds workflow coverage for a current total of 38 passing tests. The demo also ran successfully. Investigation tests cover all six expected fixture recommendations, failed/partial/unverified evidence, missing or conflicting root causes, tied fixes, unmatched environments, conservative historical risk, and absence of memory writes.

These checks establish behavior on the synthetic fixtures; they do not measure general accuracy or production recovery improvements.

## Boundaries

The current investigator is rule-based. It does not call an LLM, authorize execution, perform remediation, or write inferred outcomes into memory. See the [demo output](getting-started.md#current-demonstration).
