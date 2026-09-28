# Phase 4: recovery verification and memory feedback

[Documentation index](README.md) | [Remaining phases](roadmap.md)

**Status: implemented for local simulation.**

## Steps completed

1. Added the Reprocessing Agent, with a successful remediation prerequisite.
2. Selected transaction, job, or request retry from incident context; the scenario supplies an explicit operation ID.
3. Added independent simulated health and operation-recovery checks.
4. Added the workflow service to coordinate investigation, policy, remediation, retry, verification, and memory storage.
5. Preserved tool acknowledgements, verified step outcomes, and the overall SUCCESS/FAILED/PARTIAL result separately.
6. Added duplicate-run protection and memory-write retry without repeated execution within one workflow instance.
7. Updated the terminal demo to show a later incident retrieving the newly stored experience.

## Verification logic

- Both service health and operation recovery pass: SUCCESS.
- Only one passes: PARTIAL.
- Neither passes: FAILED.
- Remediation tool failure: skip the retry and verify current state.

New outcome records preserve the action order and observed failures. The investigator's root-cause hypothesis is retained as a hypothesis, documented in the lesson; verification checks recovery, not root-cause causality.

## Checks and limits

The full suite has **38 passing tests**, including 16 workflow tests. These cover approved execution, failures, partial recovery, tool success without recovery, repeat calls, write failures, and recalling a newly recorded incident. Tests use explicit synthetic scenario truth separate from the investigator's inputs.

The feedback demonstration proves that new records are recalled. It does not establish an accuracy or recovery-time improvement. State, approvals, and duplicate protection are synchronous and in-process; real Hindsight persistence, authentication, distributed execution, and measured evaluation are not implemented.
