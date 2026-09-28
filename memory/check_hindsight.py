"""Connection and cross-process persistence check using synthetic records only."""

import argparse
from uuid import uuid4

from config import Settings
from memory.hindsight_adapter import HindsightMemoryClient, HindsightUnavailable
from memory.memory_writer import load_datasets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="Retain one synthetic probe; may consume server LLM credits")
    group.add_argument("--read", metavar="INCIDENT_ID", help="Verify a previously written probe in a new process")
    args = parser.parse_args()
    settings = Settings.from_env()
    client = HindsightMemoryClient(settings)
    try:
        print(f"Hindsight API version: {client.check_connection()}")
        if args.write:
            _, history, _ = load_datasets(settings.data_dir)
            record = history[0].model_copy(deep=True)
            record.incident.incident_id = "PROBE-" + uuid4().hex
            for index, outcome in enumerate(record.outcomes):
                outcome.incident_id = record.incident.incident_id
                outcome.outcome_id = f"{record.incident.incident_id}-{index}"
            client.store_incident_memory(record)
            if client.get_incident_memory(record.incident.incident_id) != record:
                raise ValueError("Probe read-back does not match the written record")
            print(f"Written and verified: {record.incident.incident_id}")
            print(f"Run in a new process: python -m memory.check_hindsight --read {record.incident.incident_id}")
        if args.read:
            record = client.get_incident_memory(args.read)
            if record is None:
                raise ValueError("Probe not found in the configured bank")
            query = record.incident.model_copy(update={"incident_id": "QUERY-" + uuid4().hex})
            matches = client.retrieve_similar_incidents(query, limit=100)
            if not any(item.memory.incident.incident_id == args.read for item in matches):
                raise ValueError("Source record persisted, but semantic recall did not return it")
            print(f"Persisted source and recall verified: {args.read}; ordered outcomes={len(record.outcomes)}")
    except (HindsightUnavailable, ValueError) as exc:
        parser.exit(1, f"Check failed: {exc}\n")


if __name__ == "__main__":
    main()
