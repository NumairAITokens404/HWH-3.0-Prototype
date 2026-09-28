# Phase 5B: local LLM investigation

> Historical checkpoint: this page records the local-model milestone. See the [current architecture](architecture.md) for the completed Hindsight-centered workflow and durable approval state.

[Documentation index](README.md) | [Local setup](local-model.md)

## Implemented

1. Added an Ollama client behind the `StructuredLLM` protocol.
2. Added structured model proposals with action, hypothesis, explanation, citations, and subjective confidence.
3. Sent incident inputs and ordered historical records to the model; evaluation labels and simulator truth remain outside its prompt.
4. Validated proposals against actual citations and the deterministic historical-support checks.
5. Wired the model into investigation-only and full workflow entry points.
6. Added explicit fallback reasons for unavailable inference, malformed output, or invented citations.
7. Enabled automatic `.env` loading and an optional SQLite backend for persistent local runs.

## Recommendation boundaries

The model synthesizes a proposal. To proceed to the action decision layer, it must name the historically supported action and cite at least one supporting incident or outcome ID. A valid model abstention is respected. Unsupported proposals remain visible as advisory output and execute nothing.

Canonical historical cause, historical risk, and deterministic confidence stay separate from the model's subjective proposal. The decision layer still assigns authoritative risk and requests human approval. A model cannot set approval or execution fields. Root-cause explanations remain hypotheses.

The guarded policy intentionally limits model autonomy for this prototype. Raw proposals are separately evaluated so acceptance due to the guard or fallback is not presented as model accuracy.

## Files

| File | Purpose |
| --- | --- |
| `llm/client.py` | Bounded Ollama requests, connection checks, provider protocol, typed errors |
| `llm/prompts.py` | Evidence prompt and explicit treatment of embedded text as data |
| `llm/check.py` | Model-presence and generation smoke check |
| `schemas/llm.py` | Strict model proposal contract |
| `agents/llm_investigator.py` | Model synthesis, citation checks, support validation, fallback |
| `memory/sqlite_client.py` | Transactional local incident storage and lexical retrieval |
| `cli.py`, `main.py` | Demo, JSON investigation, simulation inputs, interactive review |
| `tests/test_llm.py`, `tests/test_local_runtime.py` | Guards, fallback, persistent writes, configuration, evaluation |

## Limits

At this checkpoint, the workflow approval cache was in-process. The current dashboard persists approvals and workflow checkpoints through `WORKFLOW_DB_PATH`. The model still does not execute operations; prompt instructions guide interpretation while Python enforces citations, policy, and execution checks.
