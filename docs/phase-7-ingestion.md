# Phase 7: incident-history ingestion

[Documentation index](README.md) | [HTTP API](api.md)

## Implemented flow

```text
Incident-history file (JSON, CSV, Markdown, text/log, or PDF)
        |
        v
Size, encoding, and schema validation
        |
        v
Complete IncidentMemory records retained
        |
        +--> failed and partial outcomes converted into bounded, traceable chunks
        |         |
        |         v
        |    Failed Remediation Memory
        |
        v
Hindsight native retention: chunking, fact extraction, and embeddings
```

JSON accepts one `IncidentMemory`, an array of records, or `{ "records": [...] }`. Uploads are limited to 500 records and `API_UPLOAD_MAX_BYTES` (5 MiB by default). Every format is normalized into the same strict `IncidentMemory` schema. Duplicate incident IDs, unknown fields, malformed data, and conflicting existing records are rejected before writing new records.

## Format contracts

- JSON uses the canonical schema directly.
- CSV uses one incident per row. Required columns are `incident_id`, `service`, `severity`, `environment`, `symptoms`, and `outcomes`. Separate symptoms with `|`; `outcomes` is a JSON array. `recommendation` is an optional JSON object. Other incident and resolution fields use matching schema names.
- Markdown and UTF-8 `.txt`/`.log` files must contain JSON inside a fenced `incident-memory` or `json` code block. Marker pairs `AII_INCIDENT_MEMORY_BEGIN` and `AII_INCIDENT_MEMORY_END` are also accepted.
- PDF files follow the same embedded-block contract after text extraction. PDFs must contain selectable text, cannot be encrypted, and are limited to 100 pages. Scanned-image OCR is outside this phase.

Free-form prose is deliberately rejected. The importer does not ask an LLM to invent missing identifiers, actions, outcomes, or verification states.

Each failed or partial outcome becomes a structure-aware chunk containing the incident, service, environment, symptoms, root-cause hypothesis, attempted action, observed result, verification state, and lesson. Large entries are split into bounded overlapping chunks. Deterministic chunk IDs make retrying the same upload idempotent.

Complete incident histories remain authoritative. Failed-remediation chunks are a search index and never replace the ordered outcomes used by the investigator.

## Embedding behavior

With `MEMORY_BACKEND=hindsight`, each complete record and failed-remediation chunk is retained as a traceable Hindsight document. Hindsight performs its own chunking and embedding during retention. [Hindsight documents and chunks](https://hindsight.vectorize.io/developer/api/documents) | [Hindsight retain pipeline](https://hindsight.vectorize.io/developer/api/retain)

With `mock` or `sqlite`, the same chunks are stored and searched using the transparent local lexical matcher. The API reports `embedding_status: NOT_AVAILABLE_LOCAL`; it does not claim that local lexical storage created embeddings.

## API behavior

- `POST /api/memory/uploads` accepts a multipart field named `file` and returns counts, incident IDs, completed stages, and embedding status.
- `GET /api/memory/failed-remediations?q=...&limit=10` searches failed and partial remediation evidence.
- Supported extensions are `.json`, `.csv`, `.md`, `.txt`, `.log`, and `.pdf`.

The live Hindsight path is adapter-tested offline. End-to-end embeddings and semantic recall still require a configured Hindsight service.
