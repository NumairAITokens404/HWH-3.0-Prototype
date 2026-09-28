# Local model and GPU setup

[Documentation index](README.md)

## Selected model

Use **Qwen3.5 9B Q4_K_M**, Ollama tag `qwen3.5:9b`, on this machine's RTX 5070 Ti Laptop GPU with 12 GB VRAM. The official package is approximately 6.6 GB. Start with an 8,192-token context and one request at a time to leave room for inference memory. Package size is not total VRAM consumption.

This is a practical fit for incident analysis and structured recommendations; it is not a claim of being best on every benchmark. We measure it on this project's fixtures. The larger 27B Q4 package alone exceeds 12 GB. Use `qwen3.5:4b` if you need more headroom while other GPU applications are open. [Official model sizes](https://ollama.com/library/qwen3.5:9b)

## Run without Docker or a paid API

Ollama is already installed on this machine. On a fresh machine, install it from [Ollama](https://ollama.com/download/windows), then:

```powershell
ollama pull qwen3.5:9b
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Set these in the project `.env` (already configured locally):

```dotenv
MEMORY_BACKEND=sqlite
SQLITE_PATH=./.runtime/incidents.sqlite3
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3.5:9b
LLM_TIMEOUT=120
LLM_CONTEXT=8192
LLM_MAX_TOKENS=1200
```

`.env` loads automatically. Existing shell variables take precedence. Relative data/database paths resolve from the project root. No API key is required for local Ollama. SQLite is a local persistent memory backend, not a Hindsight service.

```powershell
.venv\Scripts\python.exe -m llm.check --generate
.venv\Scripts\python.exe main.py
ollama ps
```

The investigator should print `llm_grounded`. If it prints `deterministic_fallback`, inspect the reason; a fallback is not a successful model run. `ollama ps` shows whether the model loaded on the GPU. Use the 8K context rather than the model's advertised maximum context on a 12 GB GPU.

## Other commands

```powershell
# Fast deterministic demonstration
.venv\Scripts\python.exe main.py --engine rules --memory mock

# Investigate an input, without executing actions
.venv\Scripts\python.exe main.py investigate --input data/examples/incident.json

# Review a simulated high-risk operation in the terminal
.venv\Scripts\python.exe main.py run --input data/examples/high-risk-scenario.json --memory mock --interactive

# Demonstrate a failed retry and partial overall recovery
.venv\Scripts\python.exe main.py run --input data/examples/failed-retry-scenario.json --memory mock

# Measure both investigators separately
.venv\Scripts\python.exe -m evaluation.evaluate_memory --engine rules --output reports/local-rules.json
.venv\Scripts\python.exe -m evaluation.evaluate_memory --engine ollama --output reports/local-ollama.json
```

Custom scenario IDs must be new when using persistent memory. The demo automatically generates new IDs. SQLite records survive restarts in `.runtime/incidents.sqlite3`; the entire `.runtime/` directory is ignored by Git.

## Generation behavior

The Ollama client requests JSON matching a Pydantic schema, disables thinking output, limits generated tokens, and uses temperature zero. It rejects malformed or truncated output and exposes a fallback reason. Schema validation alone does not establish factual correctness: citations, historical support, and action approval are checked independently. [Structured output API](https://docs.ollama.com/capabilities/structured-outputs)

To release the model's GPU allocation after using the app:

```powershell
ollama stop qwen3.5:9b
```
