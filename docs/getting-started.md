# Run the prototype

[Documentation index](README.md)

## Setup and run

Use Python 3.10 or newer. Tested locally with Python 3.13 and Pydantic 2.13.5. Install dependencies once; default mock mode runs offline without API keys. For optional persistent memory, follow [Hindsight setup](hindsight-setup.md).

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

## Current demonstration

`main.py` seeds historical memory and runs three explicit simulation scenarios. The investigator receives incident inputs, not simulator truth or expected-answer labels.

```text
DEMO-001: SUCCESS; memory_stored=True
  Recommendation: reset_customer_pin
  Evidence: INC-101, INC-102
DEMO-002: SUCCESS; memory_stored=True
  Recommendation: reset_customer_pin
  Evidence: DEMO-001, INC-101, INC-102
DEMO-003: HUMAN_APPROVAL_REQUIRED; memory_stored=False
  Recommendation: rollback_connection_pool_change
```

The demo never fabricates human approval. To inspect the full JSON result in a Python integration, call `result.model_dump_json(indent=2)` on the returned `WorkflowResult`.

## Service API and approval

Construct `IncidentWorkflow(client, world)` with seeded memory and a `SimulationWorld` containing explicit `SimulationScenario` records. Each scenario identifies its incident, operation, and required fix. Optional flags let tests independently control tool success, health, and operation recovery.

```python
from schemas.workflow import Approval

result = workflow.run(incident)
# Call this branch only after your caller has obtained a real review decision.
if result.status == "HUMAN_APPROVAL_REQUIRED":
    approval = Approval(
        request_id=result.decision.request_id,
        approved=reviewer_approved,
        reviewer=reviewer_name,
    )
    result = workflow.run(incident, approval)
```

Here `workflow`, `incident`, `reviewer_approved`, and `reviewer_name` are inputs supplied by the integrating application. This is an API example, not an automatic approval script. Approval is bound to the full incident, recommendation, and policy rule. The local prototype trusts reviewer inputs; it does not authenticate users.

Reuse the same workflow instance to resume approvals or repeat calls. Completed results are cached, and a failed memory write can be retried without rerunning actions. This guarantee is limited to the synchronous in-process instance. Workflow state is lost on exit. Mock incident memory also resets; the optional real adapter uses server-side source records.
