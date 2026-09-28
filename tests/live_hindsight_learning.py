"""Opt-in integration check using the configured Hindsight and model services.

Run: python -m tests.live_hindsight_learning
Writes synthetic records to a new isolated bank and prints a verifiable report.
"""

from dataclasses import replace
from pathlib import Path
import json
import time
from uuid import uuid4

from api.models import ApprovalSubmission
from api.runtime import ApiRuntime
from config import Settings
from services.incident_service import investigate_incident


def main():
    suffix = uuid4().hex[:10]
    root = Path(__file__).resolve().parents[1] / ".runtime" / f"learning-check-{suffix}"
    root.mkdir(parents=True, exist_ok=True)
    settings = replace(Settings.from_env(), memory_backend="hindsight", action_backend="simulation",
                       hindsight_bank_id=f"learning-check-{suffix}", workflow_db_path=root / "workflows.sqlite3")
    runtime = ApiRuntime(settings)
    report = {"bank": runtime.ui_memory.bank_id, "cases": [], "baseline": runtime.evaluation_report()["current"]["score"]}
    print(json.dumps({"stage": "connected", "bank": report["bank"], "health": runtime.memory_status()}), flush=True)
    for key in ("HELD-007", "TEST-003"):
        print(json.dumps({"stage": "learning_and_review", "incident": key}), flush=True)
        pending = runtime.start_case(key)
        assert pending.status == "HUMAN_APPROVAL_REQUIRED", pending.model_dump_json()
        assert pending.memory_stored and pending.observation_id
        assert runtime.ui_memory.get_incident_memory(pending.observation_id).record_kind == "observation"
        print(json.dumps({"stage": "approval_required", "incident": key, "risk": pending.decision.risk_level,
                          "learned_from": pending.learned_from,
                          "recalled": [item.incident_id for item in pending.investigation.historical_evidence]}), flush=True)
        result = runtime.submit_ui_approval(key, ApprovalSubmission(
            request_id=pending.decision.request_id, approved=True, reviewer="integration-check"), "integration-check")
        assert result.status == "SUCCESS" and result.memory_stored, result.model_dump_json()
        saved = runtime.ui_memory.get_incident_memory(key)
        assert saved.final_outcome == "SUCCESS"
        later = runtime.case(key).incident.model_copy(update={"incident_id": f"LATER-{key}"})
        recalled = investigate_incident(later, runtime.ui_memory, runtime.llm)
        ids = [item.incident_id for item in recalled.historical_evidence]
        assert key in ids, f"New outcome not recalled: {ids}"
        report["cases"].append({"incident": key, "status": result.status,
                                "retained_outcomes": len(saved.outcomes), "later_recalled": ids,
                                "learned_from": pending.learned_from, "action_risk": pending.decision.risk_level})
        print(json.dumps({"stage": "outcome_retained_and_recalled", **report["cases"][-1]}), flush=True)
    deadline = time.monotonic() + 600
    while runtime._evaluation_running and time.monotonic() < deadline:
        time.sleep(2)
    assert not runtime._evaluation_running, "Evaluation timed out"
    evaluation = runtime.evaluation_report()
    assert evaluation["evaluation_status"] == "ready", evaluation["evaluation_error"]
    assert evaluation["current"]["score"] > report["baseline"]
    report["current_score"] = evaluation["current"]["score"]
    report["checkpoints"] = [{"label": point["label"], "score": point["score"]} for point in evaluation["progress"]]
    reopened = ApiRuntime(settings)
    assert reopened.ui_memory.bank_id == runtime.ui_memory.bank_id
    assert reopened.case_result("HELD-007").status == "SUCCESS"
    assert reopened.ui_memory.get_incident_memory("TEST-003").final_outcome == "SUCCESS"
    report["restart_verified"] = True
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"stage": "passed", "report": str(root / "report.json"), **report}), flush=True)
    reopened.workflow_store.close()
    runtime.workflow_store.close()


if __name__ == "__main__":
    main()
