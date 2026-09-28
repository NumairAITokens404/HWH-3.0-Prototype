# Phase 10: checkpoint hardening

[Documentation index](README.md)

This checkpoint closes the remaining code-owned readiness gaps around approval identity, reproducible data inspection, connector uncertainty, and container execution.

## Approval identity

`APPROVAL_IDENTITIES_JSON` optionally maps reviewer names to bearer tokens. When it is configured, the API derives the reviewer from the token, rejects missing or invalid credentials, rejects a conflicting claimed reviewer, and writes the derived identity to the audit log. An empty mapping keeps the local demo flow available.

Example for a local `.env` file:

```text
APPROVAL_IDENTITIES_JSON={"alice":"replace-with-a-long-random-token"}
```

## Dataset checkpoint

The repository contains 18 synthetic historical incidents, 54 ordered outcomes, and 6 held-out regression cases across six balanced service families. Run:

```powershell
.venv\Scripts\python.exe -m evaluation.dataset_audit --output reports/dataset-audit.json
```

The report checks split leakage, label references, success/failure coverage, service balance, and records SHA-256 hashes for all three source files. This makes the demo dataset reproducible. It remains a small synthetic regression set and cannot support production accuracy claims; a larger de-identified, blinded dataset must come from the team or challenge owner.

## Deployment

The image now runs as an unprivileged `app` user. Compose retains only runtime SQLite state in its named volume, exposes a health check, and passes approval credentials through deployment environment variables. Static deployment checks run in the normal test suite. A real `docker compose up --build` remains the final environment check on a machine with Docker installed.

## Verification

The checkpoint suite covers token authentication and reviewer spoofing, dataset integrity, connector receipt reconciliation, and container configuration.
