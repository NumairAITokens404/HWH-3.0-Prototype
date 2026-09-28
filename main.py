"""Run an offline investigation demo using historical fixtures only."""

from config import Settings
from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from services.incident_service import investigate_incident


def main():
    incidents, history, cases = load_datasets(Settings.from_env().data_dir)
    client = MockHindsightClient()
    seed_memory(client, history)
    print(f"Validated {len(incidents)} historical incidents and {len(cases)} held-out cases.")
    query = cases[0].incident
    result = investigate_incident(query, client)
    print(result.model_dump_json(indent=2))
    print("Offline baseline only: no LLM, action execution, or recovery verification.")


if __name__ == "__main__":
    main()
