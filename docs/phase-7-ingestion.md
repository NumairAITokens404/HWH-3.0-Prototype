# Phase 7: incident-history ingestion

[Documentation index](README.md) | [HTTP API](api.md)

## Implemented flow

```text
JSON incident-history file
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

The application accepts one `IncidentMemory`, an array of records, or `{ "records": [...] }`. Uploads are limited to 500 records and `API_UPLOAD_MAX_BYTES` (5 MiB by default). It rejects invalid UTF-8, malformed JSON, duplicate incident IDs, unknown fields, and conflicting existing records before writing new records.

Each failed or partial outcome becomes a structure-aware chunk containing the incident, service, environment, symptoms, root-cause hypothesis, attempted action, observed result, verification state, and lesson. Large entries are split into bounded overlapping chunks. Deterministic chunk IDs make retrying the same upload idempotent.

Complete incident histories remain authoritative. Failed-remediation chunks are a search index and never replace the ordered outcomes used by the investigator.

## Embedding behavior

With `MEMORY_BACKEND=hindsight`, each complete record and failed-remediation chunk is retained as a traceable Hindsight document. Hindsight performs its own chunking and embedding during retention. [Hindsight documents and chunks](https://hindsight.vectorize.io/developer/api/documents) | [Hindsight retain pipeline](https://hindsight.vectorize.io/developer/api/retain)

With `mock` or `sqlite`, the same chunks are stored and searched using the transparent local lexical matcher. The API reports `embedding_status: NOT_AVAILABLE_LOCAL`; it does not claim that local lexical storage created embeddings.

## API behavior

- `POST /api/memory/uploads` accepts a multipart field named `file` and returns counts, incident IDs, completed stages, and embedding status.
- `GET /api/memory/failed-remediations?q=...&limit=10` searches failed and partial remediation evidence.
- Only `.json` uploads are accepted in this phase. PDF, Markdown, CSV, and free-form log extraction remain future work.

The live Hindsight path is adapter-tested offline. End-to-end embeddings and semantic recall still require a configured Hindsight service.
