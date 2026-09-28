"""Demonstrate simulated recovery, memory recall, and an approval pause."""

from config import Settings
from uuid import uuid4
from memory.factory import create_memory_client
from memory.memory_writer import load_datasets, seed_memory
from schemas.workflow import SimulationScenario
from services.incident_service import IncidentWorkflow
from tools.simulation import SimulationWorld


def main():
    settings = Settings.from_env()
    incidents, history, cases = load_datasets(settings.data_dir)
    client = create_memory_client(settings)
    seed_memory(client, history)
    print(f"Validated {len(incidents)} historical incidents and {len(cases)} held-out cases.")
    first = cases[0].incident.model_copy(update={"incident_id": "DEMO-001", "transaction_id": "SYN-TXN-001"})
    second = first.model_copy(update={"incident_id": "DEMO-002", "transaction_id": "SYN-TXN-002"})
    high_risk = cases[2].incident.model_copy(update={"incident_id": "DEMO-003"})
    if settings.memory_backend == "hindsight":
        suffix = uuid4().hex[:12]
        for item in (first, second, high_risk):
            item.incident_id += "-" + suffix
    # Simulator truth is separate from investigation inputs and evaluation labels.
    world = SimulationWorld([
        SimulationScenario(incident=first, operation_id="SYN-TXN-001", required_action="reset_customer_pin"),
        SimulationScenario(incident=second, operation_id="SYN-TXN-002", required_action="reset_customer_pin"),
        SimulationScenario(incident=high_risk, operation_id="SYN-REQ-003", required_action="rollback_connection_pool_change"),
    ])
    workflow = IncidentWorkflow(client, world)
    for incident in (first, second, high_risk):
        result = workflow.run(incident)
        print(f"\n{incident.incident_id}: {result.status}; memory_stored={result.memory_stored}")
        action = result.investigation.recommended_action
        if action:
            print(f"  Recommendation: {action.action_name}")
        print("  Evidence: " + ", ".join(item.incident_id for item in result.investigation.historical_evidence))
        if result.verification:
            print(f"  {result.verification.detail}")
        if result.status == "HUMAN_APPROVAL_REQUIRED":
            print("  Paused before execution. No approval is fabricated by the demo.")
    print(f"\nAll actions and observations are local simulations. Memory backend: {settings.memory_backend}.")


if __name__ == "__main__":
    main()
