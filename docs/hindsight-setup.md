# Configure and verify Hindsight

[Documentation index](README.md) | [Adapter design](phase-5-hindsight.md)

The local demo can use SQLite and Ollama without Hindsight. The following steps enable a real service. The application automatically loads the project `.env`; shell variables override it. Do not commit credentials.

## 1. Start or obtain a service

### Local Docker

Install/start Docker Desktop with Linux containers. Configure the server's LLM provider and key using the official [installation guide](https://hindsight.vectorize.io/developer/installation) and [configuration reference](https://hindsight.vectorize.io/developer/configuration). The server needs a model for extraction even though this project's investigator is still rule-based.

Once `HINDSIGHT_API_LLM_API_KEY` is set in your shell for the server's configured provider, the official all-in-one image can be started from PowerShell with a persistent named volume:

```powershell
docker run -d --name aii-hindsight --restart unless-stopped --shm-size=1g -p 127.0.0.1:8888:8888 -p 127.0.0.1:9999:9999 -e HINDSIGHT_API_LLM_API_KEY -v aii-hindsight-data:/home/hindsight/.pg0 ghcr.io/vectorize-io/hindsight:latest
docker logs aii-hindsight
```

This example uses the image's default provider/model settings; pass the provider-specific settings from the configuration reference if yours differ. Wait for startup. The API is on port 8888 and the UI on port 9999. The `latest` image can change; record or pin a tested image version for a repeatable demo. This container command has not been executed in this workspace.

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

No server error silently changes this setting. Use one writer per bank for this prototype. Workflow approvals and duplicate-run caches remain in memory even when incident history is persistent.
