"""SQLite-backed workflow checkpoints and append-only audit events."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock

from schemas.workflow import SimulationScenario, WorkflowResult
from schemas.workflow_state import AuditEvent, AuditEventType, WorkflowRunRecord, WorkflowState


class WorkflowStore:
    """Persist control-plane state independently from incident-memory storage."""

    def __init__(self, path: Path | None):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = RLock()
        self._connection = sqlite3.connect(str(path) if path is not None else ":memory:",
                                           timeout=10, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
                incident_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                scenario TEXT NOT NULL,
                result TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            self._connection.execute("""CREATE TABLE IF NOT EXISTS audit_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                details TEXT NOT NULL
            )""")
            self._connection.execute("CREATE INDEX IF NOT EXISTS audit_incident_sequence ON audit_events (incident_id, sequence)")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __del__(self):
        connection = getattr(self, "_connection", None)
        if connection is not None:
            connection.close()

    def save_run(self, scenario: SimulationScenario, result: WorkflowResult, state: WorkflowState) -> WorkflowRunRecord:
        if scenario.incident.incident_id != result.incident_id:
            raise ValueError("Workflow scenario and result incident IDs must match")
        now = datetime.now(timezone.utc)
        with self._lock, self._connection:
            existing = self._connection.execute(
                "SELECT state FROM workflow_runs WHERE incident_id = ?", (result.incident_id,)).fetchone()
            if existing is not None and existing["state"] in {"COMPLETED", "DENIED", "TERMINAL"}:
                raise ValueError("Terminal workflow state cannot be replaced")
            self._connection.execute("""INSERT INTO workflow_runs
                (incident_id, state, scenario, result, updated_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    state=excluded.state, scenario=excluded.scenario,
                    result=excluded.result, updated_at=excluded.updated_at""",
                (result.incident_id, state, scenario.model_dump_json(),
                 result.model_dump_json(), now.isoformat()))
        return WorkflowRunRecord(incident_id=result.incident_id, state=state,
                                 scenario=scenario, result=result, updated_at=now)

    def get_run(self, incident_id: str) -> WorkflowRunRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM workflow_runs WHERE incident_id = ?", (incident_id,)).fetchone()
        return self._record(row) if row is not None else None

    def pending_runs(self, limit: int) -> list[WorkflowRunRecord]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM workflow_runs WHERE state = 'PENDING_APPROVAL' ORDER BY updated_at LIMIT ?",
                (limit,)).fetchall()
        return [self._record(row) for row in rows]

    def append_event(self, incident_id: str, event_type: AuditEventType,
                     details: dict | None = None) -> AuditEvent:
        now = datetime.now(timezone.utc)
        encoded = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))
        with self._lock, self._connection:
            cursor = self._connection.execute("""INSERT INTO audit_events
                (incident_id, event_type, occurred_at, details) VALUES (?, ?, ?, ?)""",
                (incident_id, event_type, now.isoformat(), encoded))
            sequence = cursor.lastrowid
        return AuditEvent(sequence=sequence, incident_id=incident_id,
                          event_type=event_type, occurred_at=now,
                          details=json.loads(encoded))

    def events_for(self, incident_id: str) -> list[AuditEvent]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM audit_events WHERE incident_id = ? ORDER BY sequence", (incident_id,)).fetchall()
        return [AuditEvent(sequence=row["sequence"], incident_id=row["incident_id"],
                           event_type=row["event_type"], occurred_at=datetime.fromisoformat(row["occurred_at"]),
                           details=json.loads(row["details"])) for row in rows]

    @staticmethod
    def _record(row: sqlite3.Row) -> WorkflowRunRecord:
        return WorkflowRunRecord(
            incident_id=row["incident_id"], state=row["state"],
            scenario=SimulationScenario.model_validate_json(row["scenario"]),
            result=WorkflowResult.model_validate_json(row["result"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
