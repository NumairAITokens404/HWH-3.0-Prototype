"""Compare the same investigator with and without history on isolated fixtures."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

from config import Settings
from evaluation.metrics import summarize
from llm.client import create_llm
from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from services.incident_service import investigate_incident, IncidentWorkflow
from schemas.workflow import SimulationScenario
from tools.simulation import SimulationWorld


def evaluate(settings: Settings, progress=None) -> dict:
    _, history, cases = load_datasets(settings.data_dir)
    llm = create_llm(settings)
    variants = {}
    for with_memory in (False, True):
        rows = []
        label = "with_memory" if with_memory else "without_memory"
        for case in cases:
            # New store per case, no outcome writes, and no reuse of demo state.
            memory = MockHindsightClient()
            if with_memory:
                seed_memory(memory, history)
            if progress:
                progress(f"{label}: {case.incident.incident_id}")
            # Expected action is simulator truth only; never passed to the model.
            world = SimulationWorld([SimulationScenario(incident=case.incident,
                                     operation_id="EVAL-" + case.incident.incident_id,
                                     required_action=case.expected_action)])
            workflow = IncidentWorkflow(memory, world, llm).run(case.incident)
            result = workflow.investigation
            proposal = result.model_proposal
            accepted = result.recommended_action
            proposed_action = proposal.action_name if proposal else (
                accepted.action_name if accepted and llm is None else None)
            proposed_root_cause = proposal.likely_root_cause if proposal else (
                result.likely_root_cause if llm is None else None)
            rows.append({
                "incident_id": case.incident.incident_id,
                "expected_action": case.expected_action, "expected_root_cause": case.expected_root_cause,
                "avoid_actions": case.actions_to_avoid_before_remediation,
                "relevant_ids": case.relevant_incident_ids,
                "proposed_action": proposed_action,
                "proposed_root_cause": proposed_root_cause,
                "accepted_action": accepted.action_name if accepted else None,
                "retrieved_ids": [item.incident_id for item in result.historical_evidence],
                "method": result.method, "fallback_reason": result.fallback_reason,
                "llm_latency_ms": result.llm_latency_ms, "investigation": result.model_dump(),
                "tool_steps": int(workflow.remediation is not None) + int(workflow.reprocessing is not None),
                "workflow_status": workflow.status,
            })
        variants[label] = {"metrics": summarize(rows), "rows": rows}
    challenges = []
    for name in ("unknown_error", "missing_error", "conflicting_history"):
        incident = cases[0].incident.model_copy(deep=True)
        incident.incident_id = "CHALLENGE-" + name
        memory = MockHindsightClient()
        records = [item.model_copy(deep=True) for item in history]
        if name == "unknown_error":
            incident.error_code = "NEVER_SEEN_ERROR"
            incident.symptoms = ["Unfamiliar failure with insufficient diagnostic evidence"]
        elif name == "missing_error":
            incident.error_code = None
        else:
            records[1].root_cause = "a different unrelated cause"
        seed_memory(memory, records)
        if progress:
            progress(name)
        result = investigate_incident(incident, memory, llm)
        challenges.append({"name": name, "expected": "INSUFFICIENT_EVIDENCE", "actual": result.status,
                           "passed": result.status == "INSUFFICIENT_EVIDENCE", "method": result.method,
                           "fallback_reason": result.fallback_reason})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": settings.llm_provider, "model": settings.llm_model if llm else None,
        "memory_backend": "isolated_mock_for_comparison",
        "limitations": ["Six synthetic held-out inputs resemble the historical families; not a production benchmark.",
                        "No-memory proposals are advisory: the execution guard requires historical support.",
                        "Fallbacks are disclosed and must not be counted as successful model inference.",
                        "Exact root-cause text and token F1 are proxies, not semantic correctness.",
                        "Tool steps count actual simulated remediation/retry calls. Approval-required actions pause; zero calls can mean abstention, not efficiency.",
                        "No Hindsight live service or real recovery time is evaluated."],
        "variants": variants, "challenges": challenges,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["rules", "ollama"], default="rules")
    parser.add_argument("--output", type=Path, default=Path("reports/local-evaluation.json"))
    args = parser.parse_args()
    settings = replace(Settings.from_env(), llm_provider="none" if args.engine == "rules" else "ollama")
    report = evaluate(settings, lambda message: print(message, flush=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, variant in report["variants"].items():
        print(name + ": " + json.dumps(variant["metrics"]))
    print(f"Report: {args.output}")
    comparison_fallback = any(v["metrics"]["fallback_count"] for v in report["variants"].values())
    failed_challenge = any(not item["passed"] or item["method"] == "deterministic_fallback"
                           for item in report["challenges"])
    if args.engine == "ollama" and (comparison_fallback or failed_challenge):
        parser.exit(1, "Evaluation includes fallback or failed challenge results; do not treat it as a clean LLM run.\n")


if __name__ == "__main__":
    main()
