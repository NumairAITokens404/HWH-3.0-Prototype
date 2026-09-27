"""Run the Phase 1 data-validation and mock-memory smoke demonstration."""

from config import Settings
from memory.hindsight_client import MockHindsightClient
from memory.memory_retriever import retrieve_history
from memory.memory_writer import load_datasets, seed_memory
from schemas.outcome import IncidentMemory, Outcome


def main():
    incidents, history, cases = load_datasets(Settings.from_env().data_dir)
    client = MockHindsightClient()
    seed_memory(client, history)
    print(f"Phase 1: validated {len(incidents)} historical incidents and {len(cases)} held-out cases.")
    query = cases[0].incident
    matches = retrieve_history(client, query, limit=3)
    print(f"Mock retrieval for {query.incident_id} ({query.service}):")
    for match in matches:
        print(f"  {match.memory.incident.incident_id}: similarity={match.score:.3f}")
        for outcome in match.memory.outcomes:
            print(f"    {outcome.action}: {outcome.result} - {outcome.lesson_learned}")

    # An explicitly synthetic write exercises the interface, not an agent or verifier.
    client.store_incident_memory(IncidentMemory(incident=query))
    client.store_remediation_outcome(Outcome(
        outcome_id="SMOKE-001", incident_id=query.incident_id,
        action="reprocess_transaction", result="FAILED", risk_level="LOW",
        verified=False, lesson_learned="Synthetic smoke-test record; no action was executed.",
    ))
    assert len(client.retrieve_failed_actions(query.incident_id)) == 1
    print("Mock outcome write/read passed. Memory is ephemeral; fixture files are unchanged.")
    print("No agents, remediation, reprocessing, or verification were executed.")


if __name__ == "__main__":
    main()
