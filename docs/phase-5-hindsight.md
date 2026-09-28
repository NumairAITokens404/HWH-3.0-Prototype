# Phase 5A: real Hindsight adapter

[Documentation index](README.md) | [Setup](hindsight-setup.md)

**Status: adapter implemented and tested offline. Live server persistence and recall are not yet verified.** No service was configured during this implementation. LLM investigator integration remains a later part of Phase 5.

## Implementation

- `memory/hindsight_adapter.py`: official SDK transport and implementation of the existing memory contract.
- `memory/factory.py`: explicit mock/real backend selection, with no silent fallback.
- `memory/check_hindsight.py`: connection check and separate-process write/read probe.
- `config.py`, `.env.example`: backend, base URL, bank ID, API key, and timeout configuration.
- `requirements-hindsight.txt`: optional SDK pinned to the inspected version, `0.10.1`.
- `tests/test_hindsight_adapter.py`: 12 offline adapter and SDK contract tests.

## Storage and retrieval logic

1. Store each complete `IncidentMemory` as a JSON source document with a deterministic hashed incident ID.
2. Use synchronous retain and require a successful, non-background response.
3. Use recall to select source document IDs, restricted to this application's tag.
4. Fetch and validate each original document to preserve ordered attempts and exact results.
5. Rerank only the recalled candidates with the existing lexical score, preserving investigation thresholds. There is no fallback scan of local fixtures.
6. Reject conflicting incident/outcome IDs; retain the updated document when appending a new outcome.

Facts returned by recall are not treated as complete incident records. Missing or malformed source documents fail explicitly. Repeating an identical write is idempotent; document updates require a single writer because read/check/write is not atomic across processes.

The public memory contract and simulator remain separate. Hindsight adds persistent memory, not production remediation or durable workflow execution. The real demo uses unique incident IDs per run; fixture seeds are reused unchanged.

## Verification

The full suite passes **50 tests**, including the 12 new tests. The offline demo still passes. A local connection check failed cleanly because there is no running service. Offline transport tests do not prove that server-side extraction, indexing, or restart persistence works.

Run the [write/read probe](hindsight-setup.md) against a configured service to complete live verification. Retain and recall may invoke the server's configured models.

## API sources

The adapter was checked against the installed SDK's actual signatures and models and the official [Python client](https://hindsight.vectorize.io/sdks/python), [document API](https://hindsight.vectorize.io/developer/api/documents), and [retain API](https://hindsight.vectorize.io/developer/api/retain). It uses `aretain`, `arecall`, `aget_version`, and the asynchronous `documents.get_document` namespace, closing every session on its request's event loop.
