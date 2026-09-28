# Phase 1: data and memory foundations

[Documentation index](README.md) | [Next: investigation](phase-2-investigation.md)

**Status: implemented.**

## Steps completed

1. Created the Python package structure and placeholders for later components.
2. Added Pydantic incident, remediation, and outcome schemas to validate data at module boundaries.
3. Created 18 historical incidents, 6 held-out cases, and 54 ordered action outcomes across six problem families.
4. Defined the `HindsightClient` protocol and an in-memory mock with deterministic retrieval.
5. Added dataset validation, historical seeding, and outcome write/read operations.
6. Tested schema constraints, retrieval, duplicate handling, isolation, and dataset references.

## Why this comes first

The investigator needs trustworthy inputs and complete action histories. Keeping failed attempts alongside successful ones preserves the context needed to distinguish an ineffective retry from a retry after the correct fix. A provider-independent memory contract lets us replace the mock without changing its callers.

## Verification

The 11 foundation tests passed in the most recent full run. They cover data validation, retrieval across all six families, ordered outcomes, idempotent writes, conflicting IDs, defensive copies, and held-out separation.

## Boundaries

Memory is local and ephemeral. The fixtures are synthetic. This phase does not integrate the real Hindsight service or execute any remediation.

See [implementation reference](implementation.md) for contracts, dataset structure, and retrieval scoring, and [setup](getting-started.md) for commands.
