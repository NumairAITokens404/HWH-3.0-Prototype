# Phase 8: durable workflow state and audit history

[Documentation index](README.md) | [Architecture](architecture.md)

## What is durable

The control plane uses a dedicated SQLite database configured by `WORKFLOW_DB_PATH`. It stores the complete simulator scenario, original investigation, approval request, latest workflow result, and an append-only audit history.

Pending approvals are reconstructed when the API starts. The saved investigation is reused instead of invoking Ollama again, so a previously issued approval request remains bound to the exact recommendation that produced it.

Audit events cover incident receipt, investigation, recommendation, approval request and decision, remediation, reprocessing, verification, and memory update.

## Execution safety boundary

Before an approved action runs, the checkpoint moves from `PENDING_APPROVAL` to `EXECUTING`. An `EXECUTING` checkpoint is not automatically resumed after a restart because the process cannot prove whether an external side effect occurred before the interruption. This prevents an automatic duplicate action. A production connector will need provider idempotency keys or reconciliation before these checkpoints can be resumed.

Terminal checkpoints cannot be reopened or replaced.

## Docker compatibility

The workflow database is independent from the configured incident-memory backend. It works with SQLite memory, Hindsight running on the host, or a hosted Hindsight service.

`compose.yaml` mounts `/app/.runtime` in the named `adaptive-runtime` volume. Both `incidents.sqlite3` and `workflows.sqlite3` survive container replacement.

With Ollama running on the Windows host:

```powershell
docker compose up --build
```

The container reaches Ollama through `host.docker.internal:11434`. Override `DOCKER_LLM_BASE_URL` only when Ollama runs elsewhere.

For Hindsight running on the host:

```powershell
$env:MEMORY_BACKEND="hindsight"
docker compose up --build
```

The default container endpoint is `host.docker.internal:8888`. Use `DOCKER_HINDSIGHT_BASE_URL` for a different service location. Docker packaging is included but cannot be executed in this workspace until Docker Desktop is installed.
