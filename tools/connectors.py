"""Allowlisted HTTP sandbox connector with durable at-most-once receipts."""

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import RLock
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from schemas.incident import Incident
from schemas.workflow import ToolResult
from tools.risk_classifier import ACTION_POLICY


class ConnectorUnavailable(RuntimeError):
    """A connector call could not be completed or safely repeated."""


class ConnectorReceiptStore:
    def __init__(self, path: Path | None):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(str(path) if path is not None else ":memory:",
                                           timeout=10, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("""CREATE TABLE IF NOT EXISTS connector_receipts (
                idempotency_key TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('PENDING', 'COMPLETED')),
                response TEXT
            )""")

    def claim(self, key: str, fingerprint: str) -> ToolResult | None:
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM connector_receipts WHERE idempotency_key = ?", (key,)).fetchone()
            if row is None:
                self._connection.execute("INSERT INTO connector_receipts VALUES (?, ?, 'PENDING', NULL)",
                                         (key, fingerprint))
                return None
            if row["fingerprint"] != fingerprint:
                raise ValueError("Idempotency key is already bound to a different request")
            if row["state"] == "PENDING":
                raise ConnectorUnavailable(
                    "Connector operation is pending reconciliation and will not be repeated automatically")
            result = ToolResult.model_validate_json(row["response"])
            return result.model_copy(update={"receipt_replayed": True})

    def complete(self, key: str, result: ToolResult) -> None:
        with self._lock, self._connection:
            changed = self._connection.execute("""UPDATE connector_receipts
                SET state = 'COMPLETED', response = ?
                WHERE idempotency_key = ? AND state = 'PENDING'""",
                (result.model_dump_json(), key)).rowcount
            if changed != 1:
                raise ConnectorUnavailable("Connector receipt could not be completed")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __del__(self):
        connection = getattr(self, "_connection", None)
        if connection is not None:
            connection.close()


class SandboxHTTPConnector:
    """Call one configured sandbox service; user input never selects a host."""

    simulated = False

    def __init__(self, base_url: str, timeout: float, receipts: ConnectorReceiptStore,
                 transport=None, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.receipts = receipts
        self.api_key = api_key
        self._transport = transport or self._request

    def validate_incident(self, incident: Incident) -> None:
        if not incident.incident_id.strip():
            raise ValueError("Incident ID is required by the connector")

    @staticmethod
    def _identity(operation: str, payload: dict) -> tuple[str, str]:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        fingerprint = sha256(encoded.encode()).hexdigest()
        return f"{operation}-{fingerprint}", fingerprint

    def _execute(self, operation: str, endpoint: str, payload: dict, expected_action: str) -> ToolResult:
        key, fingerprint = self._identity(operation, payload)
        cached = self.receipts.claim(key, fingerprint)
        if cached is not None:
            return cached
        try:
            response = self._transport("POST", self.base_url + endpoint,
                                       {**payload, "idempotency_key": key})
            result = ToolResult.model_validate(response)
            if result.action != expected_action:
                raise ValueError("Connector response action does not match the request")
            result = result.model_copy(update={"execution_mode": "connector",
                                               "idempotency_key": key, "receipt_replayed": False})
            self.receipts.complete(key, result)
            return result
        except ConnectorUnavailable:
            raise
        except Exception:
            raise ConnectorUnavailable(
                "Connector response is uncertain; reconcile the pending receipt before retrying") from None

    def remediate(self, incident: Incident, action: str) -> ToolResult:
        rule = ACTION_POLICY.get(action)
        if rule is None:
            raise PermissionError("Action is not in the connector allowlist")
        if (incident.service.casefold(), (incident.error_code or "").casefold()) != (rule[0], rule[1].casefold()):
            raise PermissionError("Action is incompatible with the incident context")
        payload = {"incident": incident.model_dump(), "action": action}
        return self._execute("remediation", f"/v1/remediations/{quote(action, safe='')}", payload, action)

    def retry(self, incident: Incident) -> ToolResult:
        action = "retry_job" if incident.job_id else "reprocess_transaction" if incident.transaction_id else "retry_request"
        payload = {"incident": incident.model_dump(), "action": action}
        return self._execute("reprocessing", "/v1/reprocess", payload, action)

    def observation(self, incident: Incident) -> tuple[bool, bool, str]:
        query = urlencode({"incident_id": incident.incident_id})
        try:
            response = self._transport("GET", f"{self.base_url}/v1/status?{query}", None)
            healthy = response["service_healthy"]
            recovered = response["operation_recovered"]
            detail = response["detail"]
            if not isinstance(healthy, bool) or not isinstance(recovered, bool) or not isinstance(detail, str) or not detail.strip():
                raise ValueError
            return healthy, recovered, detail
        except Exception:
            raise ConnectorUnavailable("Connector status check failed") from None

    def _request(self, method: str, url: str, payload: dict | None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(url, data=data, method=method, headers=headers)
        with urlopen(request, timeout=self.timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise ConnectorUnavailable("Connector returned a non-success status")
            content = response.read(1_048_577)
            if len(content) > 1_048_576:
                raise ConnectorUnavailable("Connector response exceeds 1 MiB")
            return json.loads(content.decode("utf-8"))
