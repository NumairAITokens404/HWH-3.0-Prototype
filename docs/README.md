# Technical documentation

[Back to the project overview](../README.md)

| Document | What it covers |
| --- | --- |
| [Getting started](getting-started.md) | Setup, commands, configuration, and current demo output |
| [Architecture](architecture.md) | Agent roles, model validation, approval flow, and trust boundaries |
| [Phase 1: foundations](phase-1-foundations.md) | Schemas, synthetic data, mock memory, and checks |
| [Phase 2: investigation](phase-2-investigation.md) | Recommendation logic, evidence handling, and checks |
| [Phase 3: actions](phase-3-actions.md) | Action policy, approvals, and simulated remediation |
| [Phase 4: recovery](phase-4-recovery.md) | Retries, independent verification, outcome storage, and feedback |
| [Phase 5A: Hindsight adapter](phase-5-hindsight.md) | SDK adapter, backend selection, and offline validation |
| [Phase 5B: local LLM](phase-5-llm.md) | Ollama proposals, grounding checks, and fallback behavior |
| [Phase 6: evaluation](phase-6-evaluation.md) | Reproducible comparison, metrics, and limitations |
| [Phase 7: ingestion](phase-7-ingestion.md) | JSON uploads, validation, failed-remediation chunks, and embedding boundaries |
| [Phase 8: workflow persistence](phase-8-workflow-persistence.md) | Restart-safe approvals, execution checkpoints, audit history, and Docker storage |
| [Local model setup](local-model.md) | Qwen3.5 9B, Ollama, GPU checks, and CLI commands |
| [HTTP API](api.md) | FastAPI startup, UI endpoints, approval lifecycle, and boundaries |
| [Hindsight setup](hindsight-setup.md) | Service configuration and cross-process persistence checks |
| [Roadmap](roadmap.md) | Completed phases and the remaining live integrations |
| [Implementation reference](implementation.md) | File guide, package structure, data contracts, and mock-memory behavior |

Update the relevant phase document as code lands. Keep the root README focused on the problem, solution, demonstration, and an accurate summary of current capabilities.
