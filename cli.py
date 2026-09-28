"""Terminal interface for investigation, simulated response, and the judge demo."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4
from config import Settings
from llm.client import create_llm
from memory.factory import create_memory_client
from memory.hindsight_adapter import HindsightUnavailable
from memory.memory_writer import load_datasets, seed_memory
from schemas.workflow import Approval, SimulationScenario
from services.incident_service import IncidentWorkflow, investigate_incident
from tools.incident_tools import load_incident, load_scenario
from tools.simulation import SimulationWorld


def review_if_requested(result, workflow, incident, interactive):
    if interactive and result.status == "HUMAN_APPROVAL_REQUIRED":
        print(f"Action: {result.decision.action_name}; risk: {result.decision.risk_level}")
        reviewer = input("Reviewer name (blank cancels): ").strip()
        if reviewer:
            approved = input("Type APPROVE to authorize this simulated action: ").strip() == "APPROVE"
            result = workflow.run(incident, Approval(request_id=result.decision.request_id,
                                                   approved=approved, reviewer=reviewer))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "investigate", "run"], nargs="?", default="demo")
    parser.add_argument("--engine", choices=["rules", "ollama"], help="Override .env investigator")
    parser.add_argument("--memory", choices=["mock", "sqlite", "hindsight"], help="Override .env memory")
    parser.add_argument("--input", type=Path, help="Incident JSON for investigate; scenario JSON for run")
    parser.add_argument("--interactive", action="store_true", help="Ask for a reviewer decision when required")
    parser.add_argument("--json", action="store_true", help="Print complete structured result(s)")
    args = parser.parse_args()
    if args.interactive and args.json:
        parser.error("Use --interactive or --json separately")
    if args.command != "demo" and args.input is None:
        parser.error("--input is required for investigate/run")
    try:
        settings = Settings.from_env()
        if args.engine:
            settings = replace(settings, llm_provider="none" if args.engine == "rules" else "ollama")
        if args.memory:
            settings = replace(settings, memory_backend=args.memory)
        _, history, cases = load_datasets(settings.data_dir)
        memory = create_memory_client(settings)
        seed_memory(memory, history)
        llm = create_llm(settings)
        if args.command == "investigate":
            result = investigate_incident(load_incident(args.input), memory, llm)
            print(result.model_dump_json(indent=2))
            return
        if args.command == "run":
            scenario = load_scenario(args.input)
            workflow = IncidentWorkflow(memory, SimulationWorld([scenario]), llm)
            result = review_if_requested(workflow.run(scenario.incident), workflow, scenario.incident, args.interactive)
            print(result.model_dump_json(indent=2))
            return
        suffix = "-" + uuid4().hex[:12] if settings.memory_backend != "mock" else ""
        first = cases[0].incident.model_copy(update={"incident_id": "DEMO-001" + suffix, "transaction_id": "SYN-TXN-001"})
        second = first.model_copy(update={"incident_id": "DEMO-002" + suffix, "transaction_id": "SYN-TXN-002"})
        high = cases[2].incident.model_copy(update={"incident_id": "DEMO-003" + suffix})
        scenarios = [SimulationScenario(incident=first, operation_id="SYN-TXN-001", required_action="reset_customer_pin"),
                     SimulationScenario(incident=second, operation_id="SYN-TXN-002", required_action="reset_customer_pin"),
                     SimulationScenario(incident=high, operation_id="SYN-REQ-003", required_action="rollback_connection_pool_change")]
        workflow = IncidentWorkflow(memory, SimulationWorld(scenarios), llm)
        results = []
        for incident in (first, second, high):
            result = review_if_requested(workflow.run(incident), workflow, incident, args.interactive)
            results.append(result)
            if not args.json:
                print(f"\n{incident.incident_id}: {result.status}; memory_stored={result.memory_stored}")
                print(f"  Investigator: {result.investigation.method}; model={result.investigation.model_name}")
                if result.investigation.fallback_reason:
                    print(f"  Fallback: {result.investigation.fallback_reason}")
                action = result.investigation.recommended_action
                if action:
                    print(f"  Recommendation: {action.action_name}")
                print("  Evidence: " + ", ".join(item.incident_id for item in result.investigation.historical_evidence))
                if result.verification:
                    print(f"  {result.verification.detail}")
                if result.status == "HUMAN_APPROVAL_REQUIRED":
                    print("  Paused before execution. Use --interactive to review.")
        if args.json:
            print(json.dumps([item.model_dump() for item in results], indent=2))
        else:
            print(f"\nAll actions and observations are simulated. Memory backend: {settings.memory_backend}.")
    except (ValueError, OSError, HindsightUnavailable) as exc:
        parser.exit(1, f"Run failed: {exc}\n")


if __name__ == "__main__":
    main()
