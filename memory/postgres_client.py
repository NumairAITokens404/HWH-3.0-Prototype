"""Postgres incident memory for hosts without durable local storage."""

from contextlib import contextmanager

import psycopg

from memory.hindsight_client import MemoryMatch, MockHindsightClient
from schemas.incident import Incident
from schemas.ingestion import FailedRemediationChunk
from schemas.outcome import IncidentMemory, Outcome


class PostgresMemoryClient:
    def __init__(self, database_url: str, namespace: str):
        self.database_url = database_url
        self.namespace = namespace
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS incident_memory (
                namespace TEXT NOT NULL, incident_id TEXT NOT NULL, record TEXT NOT NULL,
                PRIMARY KEY (namespace, incident_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS failed_remediation_chunks (
                namespace TEXT NOT NULL, chunk_id TEXT NOT NULL, incident_id TEXT NOT NULL,
                record TEXT NOT NULL, PRIMARY KEY (namespace, chunk_id))""")

    @contextmanager
    def _connection(self):
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    def check_connection(self) -> None:
        with self._connection() as connection:
            connection.execute("SELECT 1").fetchone()

    def get_incident_memory(self, incident_id: str) -> IncidentMemory | None:
        with self._connection() as connection:
            row = connection.execute("SELECT record FROM incident_memory WHERE namespace = %s AND incident_id = %s",
                                     (self.namespace, incident_id)).fetchone()
        return IncidentMemory.model_validate_json(row[0]) if row else None

    def store_incident_memory(self, memory: IncidentMemory) -> None:
        memory = IncidentMemory.model_validate(memory.model_dump())
        incident_id = memory.incident.incident_id
        with self._connection() as connection:
            connection.execute("""INSERT INTO incident_memory (namespace, incident_id, record)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (self.namespace, incident_id, memory.model_dump_json()))
            row = connection.execute("SELECT record FROM incident_memory WHERE namespace = %s AND incident_id = %s",
                                     (self.namespace, incident_id)).fetchone()
            if IncidentMemory.model_validate_json(row[0]) != memory:
                raise ValueError("Incident already exists with different content")

    def store_remediation_outcome(self, outcome: Outcome) -> None:
        outcome = Outcome.model_validate(outcome.model_dump())
        with self._connection() as connection:
            row = connection.execute("""SELECT record FROM incident_memory
                WHERE namespace = %s AND incident_id = %s FOR UPDATE""",
                (self.namespace, outcome.incident_id)).fetchone()
            if row is None:
                raise KeyError(f"Unknown incident: {outcome.incident_id}")
            memory = IncidentMemory.model_validate_json(row[0])
            for previous in memory.outcomes:
                if previous.outcome_id == outcome.outcome_id:
                    if previous != outcome:
                        raise ValueError("Conflicting outcome ID")
                    return
            memory.outcomes.append(outcome)
            connection.execute("""UPDATE incident_memory SET record = %s
                WHERE namespace = %s AND incident_id = %s""",
                (memory.model_dump_json(), self.namespace, outcome.incident_id))

    def retrieve_similar_incidents(self, incident: Incident, limit: int = 5) -> list[MemoryMatch]:
        ranking = MockHindsightClient()
        with self._connection() as connection:
            rows = connection.execute("SELECT record FROM incident_memory WHERE namespace = %s ORDER BY incident_id",
                                      (self.namespace,)).fetchall()
        for (content,) in rows:
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
            for chunk in validated:
                connection.execute("""INSERT INTO failed_remediation_chunks (namespace, chunk_id, incident_id, record)
                    VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    (self.namespace, chunk.chunk_id, chunk.incident_id, chunk.model_dump_json()))
                row = connection.execute("""SELECT record FROM failed_remediation_chunks
                    WHERE namespace = %s AND chunk_id = %s""", (self.namespace, chunk.chunk_id)).fetchone()
                if FailedRemediationChunk.model_validate_json(row[0]) != chunk:
                    raise ValueError("Conflicting failed-remediation chunk ID")

    def retrieve_failed_remediation_chunks(self, query: str, limit: int = 10) -> list[FailedRemediationChunk]:
        ranking = MockHindsightClient()
        with self._connection() as connection:
            rows = connection.execute("""SELECT record FROM failed_remediation_chunks
                WHERE namespace = %s ORDER BY chunk_id""", (self.namespace,)).fetchall()
        ranking.store_failed_remediation_chunks([FailedRemediationChunk.model_validate_json(row[0]) for row in rows])
        return ranking.retrieve_failed_remediation_chunks(query, limit)
