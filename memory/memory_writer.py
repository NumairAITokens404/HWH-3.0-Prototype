"""Validate and seed synthetic historical data into any memory adapter."""

import json
from pathlib import Path

from pydantic import TypeAdapter

from memory.hindsight_client import HindsightClient
from schemas.incident import EvaluationCase, Incident
from schemas.outcome import IncidentMemory


def load_datasets(data_dir: Path) -> tuple[list[Incident], list[IncidentMemory], list[EvaluationCase]]:
    def read(name, model):
        return TypeAdapter(list[model]).validate_python(json.loads((data_dir / name).read_text(encoding="utf-8")))

    incidents = read("incidents.json", Incident)
    history = read("remediation_history.json", IncidentMemory)
    cases = read("test_incidents.json", EvaluationCase)
    ids = [item.incident_id for item in incidents]
    history_ids = [item.incident.incident_id for item in history]
    test_ids = [item.incident.incident_id for item in cases]
    for group in (ids, history_ids, test_ids):
        if len(group) != len(set(group)):
            raise ValueError("Duplicate incident IDs in dataset")
    if set(ids) != set(history_ids):
        raise ValueError("History must cover exactly the historical incidents")
    if set(ids) & set(test_ids):
        raise ValueError("Held-out incidents must not appear in historical memory")
    by_id = {item.incident_id: item for item in incidents}
    if any(record.incident != by_id[record.incident.incident_id] for record in history):
        raise ValueError("History incident content does not match incidents.json")
    if any(not set(case.relevant_incident_ids) <= set(ids) for case in cases):
        raise ValueError("Evaluation labels reference unknown historical incidents")
    return incidents, history, cases


def seed_memory(client: HindsightClient, history: list[IncidentMemory]) -> None:
    for record in history:
        client.store_incident_memory(record)
