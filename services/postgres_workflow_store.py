"""Postgres workflow checkpoints and audit events for ephemeral app hosts."""

from datetime import datetime, timezone
import json

import psycopg
from psycopg.rows import dict_row

from schemas.workflow import SimulationScenario, WorkflowResult
from schemas.workflow_state import AuditEvent, AuditEventType, WorkflowRunRecord, WorkflowState


class PostgresWorkflowStore:
    def __init__(self, database_url: str):
        self.database_url = database_url
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
                incident_id TEXT PRIMARY KEY, state TEXT NOT NULL, scenario TEXT NOT NULL,
                result TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS audit_events (
                sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                incident_id TEXT NOT NULL, event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL, details TEXT NOT NULL)""")
            connection.execute("""CREATE INDEX IF NOT EXISTS audit_incident_sequence
                ON audit_events (incident_id, sequence)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS dashboard_state (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""")

    def _connection(self):
        return psycopg.connect(self.database_url, connect_timeout=5, row_factory=dict_row)

    def load_dashboard(self, key: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute("SELECT value FROM dashboard_state WHERE key = %s", (key,)).fetchone()
        return json.loads(row["value"]) if row else None

    def save_dashboard(self, key: str, state: dict) -> None:
        with self._connection() as connection:
            connection.execute("""INSERT INTO dashboard_state (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                (key, json.dumps(state)))

    def close(self) -> None:
        pass

    def save_run(self, scenario: SimulationScenario, result: WorkflowResult, state: WorkflowState) -> WorkflowRunRecord:
        if scenario.incident.incident_id != result.incident_id:
            raise ValueError("Workflow scenario and result incident IDs must match")
        now = datetime.now(timezone.utc)
        with self._connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (result.incident_id,))
            existing = connection.execute("""SELECT state FROM workflow_runs
                WHERE incident_id = %s FOR UPDATE""", (result.incident_id,)).fetchone()
            if existing is not None and existing["state"] in {"COMPLETED", "DENIED", "TERMINAL"}:
                raise ValueError("Terminal workflow state cannot be replaced")
            connection.execute("""INSERT INTO workflow_runs
                (incident_id, state, scenario, result, updated_at) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (incident_id) DO UPDATE SET
                    state = EXCLUDED.state, scenario = EXCLUDED.scenario,
                    result = EXCLUDED.result, updated_at = EXCLUDED.updated_at""",
                (result.incident_id, state, scenario.model_dump_json(),
                 result.model_dump_json(), now.isoformat()))
        return WorkflowRunRecord(incident_id=result.incident_id, state=state,
                                 scenario=scenario, result=result, updated_at=now)

    def get_run(self, incident_id: str) -> WorkflowRunRecord | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM workflow_runs WHERE incident_id = %s",
                                     (incident_id,)).fetchone()
        return self._record(row) if row is not None else None

    def pending_runs(self, limit: int) -> list[WorkflowRunRecord]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._connection() as connection:
            rows = connection.execute("""SELECT * FROM workflow_runs WHERE state = 'PENDING_APPROVAL'
                ORDER BY updated_at LIMIT %s""", (limit,)).fetchall()
        return [self._record(row) for row in rows]

    def append_event(self, incident_id: str, event_type: AuditEventType,
                     details: dict | None = None) -> AuditEvent:
        now = datetime.now(timezone.utc)
        encoded = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))
        with self._connection() as connection:
            row = connection.execute("""INSERT INTO audit_events
                (incident_id, event_type, occurred_at, details) VALUES (%s, %s, %s, %s)
                RETURNING sequence""", (incident_id, event_type, now.isoformat(), encoded)).fetchone()
        return AuditEvent(sequence=row["sequence"], incident_id=incident_id,
                          event_type=event_type, occurred_at=now, details=json.loads(encoded))

    def events_for(self, incident_id: str) -> list[AuditEvent]:
        with self._connection() as connection:
            rows = connection.execute("""SELECT * FROM audit_events
                WHERE incident_id = %s ORDER BY sequence""", (incident_id,)).fetchall()
        return [AuditEvent(sequence=row["sequence"], incident_id=row["incident_id"],
                           event_type=row["event_type"], occurred_at=datetime.fromisoformat(row["occurred_at"]),
                           details=json.loads(row["details"])) for row in rows]

    @staticmethod
    def _record(row: dict) -> WorkflowRunRecord:
        return WorkflowRunRecord(
            incident_id=row["incident_id"], state=row["state"],
            scenario=SimulationScenario.model_validate_json(row["scenario"]),
            result=WorkflowResult.model_validate_json(row["result"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
