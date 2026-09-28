"""Durable local memory for a Docker-free demo; this is not Hindsight."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from memory.hindsight_client import MemoryMatch, MockHindsightClient
from schemas.incident import Incident
from schemas.ingestion import FailedRemediationChunk
from schemas.outcome import IncidentMemory, Outcome


class SQLiteMemoryClient:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS incidents (incident_id TEXT PRIMARY KEY, record TEXT NOT NULL)")
            connection.execute("""CREATE TABLE IF NOT EXISTS failed_remediation_chunks (
                               chunk_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, record TEXT NOT NULL)""")

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get_incident_memory(self, incident_id: str) -> IncidentMemory | None:
        with self._connection() as connection:
            row = connection.execute("SELECT record FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        return IncidentMemory.model_validate_json(row[0]) if row else None

    def store_incident_memory(self, memory: IncidentMemory) -> None:
        memory = IncidentMemory.model_validate(memory.model_dump())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT record FROM incidents WHERE incident_id = ?", (memory.incident.incident_id,)).fetchone()
            if row:
                if IncidentMemory.model_validate_json(row[0]) != memory:
                    raise ValueError("Incident already exists with different content")
                return
            connection.execute("INSERT INTO incidents VALUES (?, ?)", (memory.incident.incident_id, memory.model_dump_json()))

    def store_remediation_outcome(self, outcome: Outcome) -> None:
        outcome = Outcome.model_validate(outcome.model_dump())
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT record FROM incidents WHERE incident_id = ?", (outcome.incident_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown incident: {outcome.incident_id}")
            memory = IncidentMemory.model_validate_json(row[0])
            for previous in memory.outcomes:
                if previous.outcome_id == outcome.outcome_id:
                    if previous != outcome:
                        raise ValueError("Conflicting outcome ID")
                    return
            memory.outcomes.append(outcome)
            connection.execute("UPDATE incidents SET record = ? WHERE incident_id = ?", (memory.model_dump_json(), outcome.incident_id))

    def retrieve_similar_incidents(self, incident: Incident, limit: int = 5) -> list[MemoryMatch]:
        ranking = MockHindsightClient()
        with self._connection() as connection:
            for (content,) in connection.execute("SELECT record FROM incidents ORDER BY incident_id"):
                ranking.store_incident_memory(IncidentMemory.model_validate_json(content))
        return ranking.retrieve_similar_incidents(incident, limit)

    def _outcomes(self, incident_id: str, result: str) -> list[Outcome]:
        record = self.get_incident_memory(incident_id)
        if record is None:
            raise KeyError(f"Unknown incident: {incident_id}")
        return [item for item in record.outcomes if item.result == result]

    def retrieve_failed_actions(self, incident_id: str) -> list[Outcome]:
        return self._outcomes(incident_id, "FAILED")

    def retrieve_successful_actions(self, incident_id: str) -> list[Outcome]:
        return self._outcomes(incident_id, "SUCCESS")

    def store_failed_remediation_chunks(self, chunks: list[FailedRemediationChunk]) -> None:
        validated = [FailedRemediationChunk.model_validate(item.model_dump()) for item in chunks]
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for chunk in validated:
                row = connection.execute("SELECT record FROM failed_remediation_chunks WHERE chunk_id = ?",
                                         (chunk.chunk_id,)).fetchone()
                if row:
                    if FailedRemediationChunk.model_validate_json(row[0]) != chunk:
                        raise ValueError("Conflicting failed-remediation chunk ID")
                    continue
                connection.execute("INSERT INTO failed_remediation_chunks VALUES (?, ?, ?)",
                                   (chunk.chunk_id, chunk.incident_id, chunk.model_dump_json()))

    def retrieve_failed_remediation_chunks(self, query: str, limit: int = 10) -> list[FailedRemediationChunk]:
        ranking = MockHindsightClient()
        with self._connection() as connection:
            rows = connection.execute("SELECT record FROM failed_remediation_chunks ORDER BY chunk_id").fetchall()
        ranking.store_failed_remediation_chunks([FailedRemediationChunk.model_validate_json(row[0]) for row in rows])
        return ranking.retrieve_failed_remediation_chunks(query, limit)
