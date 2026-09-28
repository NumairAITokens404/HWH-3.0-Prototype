# Run the prototype

[Documentation index](README.md)

## Setup

Use Python 3.10 or newer. The rules engine and mock or SQLite memory need no API key. The local model path also needs Ollama and `qwen3.5:9b`.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

For the full local stack, set these values in `.env`:

```dotenv
MEMORY_BACKEND=sqlite
SQLITE_PATH=./.runtime/incidents.sqlite3
LLM_PROVIDER=ollama
LLM_MODEL=qwen3.5:9b
LLM_CONTEXT=8192
```

The application loads `.env` automatically. Existing shell variables take precedence. Relative data and database paths resolve from the project root.

## Choose a run mode

```powershell
# Full local demo: Ollama + durable SQLite memory
ollama pull qwen3.5:9b
.venv\Scripts\python.exe -m llm.check --generate
.venv\Scripts\python.exe main.py

# Fast deterministic demo: no model or persistent database
.venv\Scripts\python.exe main.py --engine rules --memory mock

# Read-only investigation from JSON
.venv\Scripts\python.exe main.py investigate --input data/examples/incident.json

# Simulated high-risk workflow with a terminal approval decision
.venv\Scripts\python.exe main.py run --input data/examples/high-risk-scenario.json --memory mock --interactive

# Simulated partial recovery after a failed retry
.venv\Scripts\python.exe main.py run --input data/examples/failed-retry-scenario.json --memory mock
```

The demo runs two low-risk recoveries and one high-risk approval pause. Persistent demo IDs are generated automatically. Custom scenarios need unique incident IDs when stored in SQLite.

## Approval boundary

The terminal asks for a reviewer only when `--interactive` is present. The reviewer must type `APPROVE`; otherwise the workflow stops without executing the action. Approval is bound to the incident, action, risk level, and policy rule. This prototype trusts the supplied reviewer name and does not provide user authentication.

## Verify and evaluate

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m evaluation.evaluate_memory --engine rules --output reports/local-rules.json
.venv\Scripts\python.exe -m evaluation.evaluate_memory --engine ollama --output reports/local-ollama.json
ollama ps
```

Generated reports and the `.runtime/` SQLite database are local artifacts ignored by Git. See [local model setup](local-model.md) and [evaluation](phase-6-evaluation.md) for details.

All action tools, observations, incidents, and recovery results are simulated or synthetic.
