# Configure and verify Hindsight

[Documentation index](README.md) | [Adapter design](phase-5-hindsight.md)

The local demo can use SQLite and Ollama without Hindsight. The following steps enable a real service. The application automatically loads the project `.env`; shell variables override it. Do not commit credentials.

## 1. Start or obtain a service

### Local Docker

Install/start Docker Desktop with Linux containers. Configure the server's LLM provider and key using the official [installation guide](https://hindsight.vectorize.io/developer/installation) and [configuration reference](https://hindsight.vectorize.io/developer/configuration). Hindsight uses a model for memory extraction. The separate incident investigator uses a deterministic evidence baseline with guarded Ollama synthesis when configured.

For a fully local setup, Hindsight runs in Docker and calls Ollama on the Windows host. This needs no API key. Pull the lightweight extraction model first:

```powershell
ollama pull qwen3:4b
docker run -d --name aii-hindsight --restart unless-stopped --shm-size=1g `
  -p 127.0.0.1:8888:8888 -p 127.0.0.1:9999:9999 `
  -e HINDSIGHT_API_WORKER_ID=aii-hindsight `
  -e HINDSIGHT_API_LLM_PROVIDER=ollama `
  -e HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:11434/v1 `
  -e HINDSIGHT_API_LLM_MODEL=qwen3:4b `
  -e HINDSIGHT_API_ENABLE_OBSERVATIONS=false `
  -e HINDSIGHT_API_ENABLE_AUTO_CONSOLIDATION=false `
  -e HINDSIGHT_API_CONSOLIDATION_RECONCILE_INTERVAL_SECONDS=0 `
  -e HINDSIGHT_API_MENTAL_MODEL_REFRESH_TICK_SECONDS=0 `
  -v aii-hindsight-data:/home/hindsight/.pg0 `
  ghcr.io/vectorize-io/hindsight:latest
docker logs aii-hindsight
```

This keeps Hindsight's real extraction, embeddings, storage, and recall. It disables optional observation consolidation because that background workload competes with interactive ingestion on one local GPU. The incident investigator may still use the larger `qwen3.5:9b` configured in the project `.env`. Wait for startup. The API is on port 8888 and the Hindsight UI on port 9999.

### Hosted service

Alternatively, provision a bank through [Hindsight Cloud](https://ui.hindsight.vectorize.io/) and use the endpoint/key supplied by that service. Use a dedicated synthetic-demo bank.

## 2. Install the optional client

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-hindsight.txt
```

If the virtual environment has no pip:

```powershell
python -m pip --python .venv\Scripts\python.exe install -r requirements-hindsight.txt
```

## 3. Configure the application

```powershell
$env:MEMORY_BACKEND = "hindsight"
$env:HINDSIGHT_BASE_URL = "http://localhost:8888"
$env:HINDSIGHT_BANK_ID = "adaptive-incident-intelligence"
$env:HINDSIGHT_TIMEOUT = "120"
```

For a hosted/authenticated service, additionally set `HINDSIGHT_API_KEY` through your normal secret-management method. This client token is distinct from the server's `HINDSIGHT_API_LLM_API_KEY`. Never paste either into tracked files.

## 4. Check the connection

```powershell
.venv\Scripts\python.exe -m memory.check_hindsight
```

This prints the API version. It does not verify retention permissions or the server's model credentials; the next step does.

Installing `hindsight-client` installs only the Python SDK. It does not start the Hindsight server. If the connection check fails and nothing is listening on port 8888, start the local container/service or configure a hosted `HINDSIGHT_BASE_URL` and key.

The FastAPI process starts even while Hindsight is unavailable. In that state, `GET /api/health` returns `status: degraded` and `memory_ready: false`; upload and recall operations continue to fail explicitly until Hindsight becomes reachable. The application never silently substitutes SQLite or mock memory.

## 5. Verify persistence and recall

Write one synthetic probe (this can consume server model credits):

```powershell
.venv\Scripts\python.exe -m memory.check_hindsight --write
```

Copy the printed probe ID. In a new process with the same configuration, run:

```powershell
.venv\Scripts\python.exe -m memory.check_hindsight --read PROBE-ID-FROM-OUTPUT
```

The read command requires both the exact source record and semantic recall to return the incident. To test server-restart persistence locally, restart the container and repeat the read after it is ready:

```powershell
docker restart aii-hindsight
```

Probes remain in the selected bank. Use a dedicated demo bank and manage it through the service UI. The script does not delete records.

## 6. Run the complete simulated workflow

```powershell
.venv\Scripts\python.exe main.py
```

This seeds 18 synthetic histories and retains two new demo outcomes if recommendations succeed. Unlike the mock, real recall may produce different candidate sets or insufficient evidence. First-run extraction may take time. The high-risk scenario must still wait for approval. Actions and observations remain simulated.

## Switch back to offline mode

```powershell
$env:MEMORY_BACKEND = "mock"
.venv\Scripts\python.exe main.py
```

No server error silently changes this setting. Use one writer per bank for this prototype. The dashboard's active bank ID, upload index, pending approvals, completed workflows, and evaluation state persist through `WORKFLOW_DB_PATH`; Hindsight remains the source of incident evidence and learned outcomes.
