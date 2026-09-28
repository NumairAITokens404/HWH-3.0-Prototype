"""Create a reproducible quality report for the synthetic dataset."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from config import Settings
from memory.memory_writer import load_datasets


def audit(data_dir: Path) -> dict:
    incidents, history, cases = load_datasets(data_dir)
    history_ids = {item.incident_id for item in incidents}
    test_ids = {case.incident.incident_id for case in cases}
    payload_hashes = {
        name: hashlib.sha256((data_dir / name).read_bytes()).hexdigest()
        for name in ("incidents.json", "remediation_history.json", "test_incidents.json")
    }
    services = Counter(item.service for item in incidents)
    test_services = Counter(case.incident.service for case in cases)
    outcomes = Counter(outcome.result for record in history for outcome in record.outcomes)
    checks = {
        "history_and_test_ids_disjoint": history_ids.isdisjoint(test_ids),
        "all_test_references_exist": all(set(case.relevant_incident_ids) <= history_ids for case in cases),
        "every_history_record_has_failure_and_success": all(
            {outcome.result for outcome in record.outcomes} >= {"FAILED", "SUCCESS"} for record in history),
        "every_history_service_has_test_coverage": set(services) <= set(test_services),
        "balanced_history_services": len(set(services.values())) == 1,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_kind": "synthetic_prototype",
        "counts": {"historical_incidents": len(incidents), "held_out_cases": len(cases),
                   "outcomes": sum(outcomes.values())},
        "history_services": dict(sorted(services.items())),
        "held_out_services": dict(sorted(test_services.items())),
        "outcomes_by_result": dict(sorted(outcomes.items())),
        "checks": checks,
        "passed": all(checks.values()),
        "sha256": payload_hashes,
        "limitations": [
            "Synthetic fixtures cover six known incident families.",
            "Six held-out cases are sufficient for deterministic regression, not statistical claims.",
            "Production validation requires de-identified real incidents and blinded labels.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("reports/dataset-audit.json"))
    args = parser.parse_args()
    report = audit(Settings.from_env().data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"]), "passed=" + str(report["passed"]))
    if not report["passed"]:
        parser.exit(1, "Dataset audit failed\n")


if __name__ == "__main__":
    main()
