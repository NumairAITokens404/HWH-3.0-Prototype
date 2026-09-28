# Phase 9: sandbox connectors and idempotent execution

[Documentation index](README.md) | [Action policy](phase-3-actions.md) | [Workflow persistence](phase-8-workflow-persistence.md)

## Execution modes

`ACTION_BACKEND=simulation` remains the default. It runs the deterministic local simulator used by tests and demonstrations.

`ACTION_BACKEND=connector` sends only policy-authorized actions to one administrator-configured sandbox service. Incident or model input cannot select the host, URL path, or action outside the fixed allowlist. `CONNECTOR_API_KEY` is optional and is sent as a bearer token when configured.

## Connector contract

The sandbox service implements:

| Request | Response |
| --- | --- |
| `POST /v1/remediations/{allowlisted_action}` with the incident, action, and `idempotency_key` | A valid `ToolResult` object |
| `POST /v1/reprocess` with the incident, derived retry action, and `idempotency_key` | A valid `ToolResult` object |
| `GET /v1/status?incident_id=...` | `{ "service_healthy": bool, "operation_recovered": bool, "detail": "..." }` |
| `GET /v1/receipts/{idempotency_key}` | `{ "state": "PENDING" }` or `{ "state": "COMPLETED", "result": ToolResult }` |

Responses are limited to 1 MiB, validated before use, and must identify the requested action. Tool acknowledgements still do not prove recovery; the independent status request decides the final outcome.

## At-most-once boundary

Before a side-effecting request leaves the process, its deterministic idempotency key and request fingerprint are stored in `CONNECTOR_RECEIPT_DB_PATH` with state `PENDING`.

- A completed receipt returns the stored result without another network request.
- A key bound to different request content is rejected.
- A timeout, process interruption, or invalid response leaves the receipt pending.
- Pending receipts are never retried automatically because the remote side effect may already have occurred.

This provides local at-most-once dispatch. The `reconcile(idempotency_key)` operation queries the sandbox receipt endpoint and completes the local receipt only after the remote result matches the original key. A production connector must honor the supplied idempotency identity before an uncertain operation is cleared.

## Docker configuration

`compose.yaml` stores connector receipts in the existing `adaptive-runtime` volume and reaches a host sandbox at `host.docker.internal:9000` by default.

```powershell
$env:ACTION_BACKEND="connector"
$env:CONNECTOR_API_KEY="set-through-your-secret-manager"
docker compose up --build
```

Use `DOCKER_CONNECTOR_BASE_URL` when the sandbox runs elsewhere. Keep real production services outside this prototype until connector authentication, reconciliation, and service-specific authorization have been reviewed.
