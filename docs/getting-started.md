# Run the prototype

[Documentation index](README.md)

## Setup and run

Use Python 3.10 or newer. Tested locally with Python 3.13 and Pydantic 2.13.5. Install dependencies once; the demo then runs offline without API keys.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
.venv/bin/python -m unittest discover -s tests -v
```

If virtual-environment creation cannot bootstrap pip but creates its Python executable, an existing system pip can install the dependencies with:

```powershell
python -m pip --python .venv\Scripts\python.exe install -r requirements.txt
```

Configuration comes from `INCIDENT_DATA_DIR`, which defaults to the `data/` directory beside `config.py`. Relative overrides resolve against the current working directory. `.env.example` documents the variable; the application does not automatically load `.env` files.

### Current demonstration

`main.py` validates datasets, seeds historical memory, and passes only the held-out incident input to `investigate_incident`. The customer PIN case produces these key fields, alongside complete ordered evidence and action counts:

```json
{
  "incident_id": "TEST-001",
  "status": "RECOMMENDATION_READY",
  "likely_root_cause": "stale PIN master data",
  "recommended_action": {
    "action_name": "reset_customer_pin",
    "risk_level": "LOW",
    "confidence": 0.636
  },
  "execution_authorized": false,
  "method": "deterministic_history_baseline"
}
```

Evidence comes from `INC-101` and `INC-102`; the staging incident is excluded. Both show retry failure before the fix and retry success afterward. The demo does not execute actions or write inferred outcomes into memory.
