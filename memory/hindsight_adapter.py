"""Real Hindsight adapter: retain complete records and recall source documents.

The source document is authoritative for ordered action history. Extracted fact
text is never parsed into fabricated IncidentMemory records. Single writer only:
the read/check/write protocol does not provide atomic concurrent updates.
"""

import asyncio
from hashlib import sha256
from threading import Thread
from typing import Protocol
from types import SimpleNamespace

from config import Settings
from memory.hindsight_client import MemoryMatch, MockHindsightClient
from schemas.incident import Incident
from schemas.ingestion import FailedRemediationChunk
from schemas.outcome import IncidentMemory, Outcome


class HindsightUnavailable(RuntimeError):
    """Service failure with a sanitized message; never silently fall back."""


class Transport(Protocol):
    def call(self, operation: str, **kwargs): ...


class SDKTransport:
    """Run each SDK request and close its session on one short-lived event loop.

    This is a synchronous adapter. If called while an event loop is already
    running (for example, during a FastAPI factory), the request is isolated
    in a short-lived worker thread so the SDK can own its event loop.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def call(self, operation: str, **kwargs):
        try:
            from hindsight_client import Hindsight
            from hindsight_client_api.exceptions import ApiException
        except ImportError:
            raise HindsightUnavailable("Install requirements-hindsight.txt to use the real backend") from None

        async def request():
            client = Hindsight(base_url=self.settings.hindsight_base_url,
                               api_key=self.settings.hindsight_api_key,
                               timeout=self.settings.hindsight_timeout, max_attempts=1)
            try:
                if operation == "get_document":
                    try:
                        response = await client.documents.get_document(
                            **kwargs, _request_timeout=self.settings.hindsight_timeout)
                    except ApiException as exc:
                        if exc.status == 404:
                            return None
                        raise
                    if response.original_text is None:
                        raise ValueError("Document exists but original text is unavailable")
                    return response.original_text
                if operation == "retain":
                    return await client.aretain(**kwargs)
                if operation == "recall":
                    try:
                        return await client.arecall(**kwargs)
                    except ApiException as exc:
                        # Hindsight creates banks on first retain. A new bank is
                        # empty, not an unavailable service.
                        if exc.status == 404 and "Bank '" in (exc.body or "") and "not found" in (exc.body or ""):
                            return SimpleNamespace(results=[])
                        raise
                if operation == "version":
                    return await client.aget_version()
                raise ValueError("Unknown transport operation")
            finally:
                await client.aclose()

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(request())

            result = {}
            def run_in_thread():
                try:
                    result["value"] = asyncio.run(request())
                except BaseException as exc:  # propagate into the sanitizing boundary below
                    result["error"] = exc

            worker = Thread(target=run_in_thread, name="hindsight-sdk", daemon=True)
            worker.start()
            worker.join()
            if "error" in result:
                raise result["error"]
            return result["value"]
        except Exception as exc:
            status = f" (HTTP {exc.status})" if isinstance(exc, ApiException) else ""
            raise HindsightUnavailable(f"Hindsight {operation} failed{status}; check server availability, credentials, and timeout") from None


def document_id(incident_id: str) -> str:
    return "aii-" + sha256(incident_id.encode()).hexdigest()


def failed_chunk_document_id(chunk_id: str) -> str:
    return "aii-failed-" + sha256(chunk_id.encode()).hexdigest()


class HindsightMemoryClient:
    def __init__(self, settings: Settings, transport: Transport | None = None):
        self.bank_id = settings.hindsight_bank_id
        self.transport = transport or SDKTransport(settings)

    def check_connection(self) -> str:
        return self.transport.call("version").api_version

    def _read_document(self, key: str) -> IncidentMemory | None:
        content = self.transport.call("get_document", bank_id=self.bank_id, document_id=key)
        if content is None:
            return None
        try:
            record = IncidentMemory.model_validate_json(content)
        except (ValueError, TypeError):
            raise ValueError("Hindsight source document is not a valid incident record") from None
        if document_id(record.incident.incident_id) != key:
            raise ValueError("Hindsight document ID does not match its incident")
        return record

    def get_incident_memory(self, incident_id: str) -> IncidentMemory | None:
        return self._read_document(document_id(incident_id))

    def _retain(self, memory: IncidentMemory) -> None:
        response = self.transport.call("retain", bank_id=self.bank_id, document_id=document_id(memory.incident.incident_id),
                            content=memory.model_dump_json(), retain_async=False,
                            context="Synthetic incident history. Preserve failed actions and their order. Root causes may be hypotheses.",
                            metadata={"incident_id": memory.incident.incident_id, "schema": "aii-v1"},
                            tags=["aii-v1", memory.record_kind, f"service:{memory.incident.service}",
                                  f"environment:{memory.incident.environment}"])
        if not response.success or response.var_async:
            raise HindsightUnavailable("Hindsight did not confirm synchronous retention")

    def store_incident_memory(self, memory: IncidentMemory) -> None:
        memory = IncidentMemory.model_validate(memory.model_dump())
        existing = self.get_incident_memory(memory.incident.incident_id)
        if existing is not None:
            if existing != memory:
                raise ValueError("Incident already exists with different content")
            return
        self._retain(memory)

    def store_remediation_outcome(self, outcome: Outcome) -> None:
        outcome = Outcome.model_validate(outcome.model_dump())
        memory = self.get_incident_memory(outcome.incident_id)
        if memory is None:
            raise KeyError(f"Unknown incident: {outcome.incident_id}")
        for existing in memory.outcomes:
            if existing.outcome_id == outcome.outcome_id:
                if existing != outcome:
                    raise ValueError("Conflicting outcome ID")
                return
        memory.outcomes.append(outcome)
        self._retain(memory)

    def retrieve_similar_incidents(self, incident: Incident, limit: int = 5) -> list[MemoryMatch]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        response = self.transport.call("recall", bank_id=self.bank_id,
                                       query=(f"Find incident recovery history for service {incident.service}, "
                                              f"environment {incident.environment}, error {incident.error_code}. "
                                              f"Symptoms: {'; '.join(incident.symptoms)}. "
                                              "Include original incident document IDs, failed attempts, "
                                              "successful fixes and verified reprocessing outcomes."),
                                       types=["world", "experience"], budget="high", max_tokens=8192,
                                       tags=["aii-v1"], tags_match="all_strict")
        keys = dict.fromkeys(item.document_id for item in response.results
                             if item.document_id and item.document_id.startswith("aii-")
                             and not item.document_id.startswith("aii-failed-"))
        # Hindsight selects the candidates; the existing transparent score is used
        # only to rerank those documents, keeping investigation thresholds stable.
        candidates = MockHindsightClient()
        for key in keys:
            record = self._read_document(key)
            if record is None:
                raise ValueError("Hindsight recalled an incident whose source document is missing")
            candidates.store_incident_memory(record)
        return candidates.retrieve_similar_incidents(incident, limit)

    def _outcomes(self, incident_id: str, result: str) -> list[Outcome]:
        memory = self.get_incident_memory(incident_id)
        if memory is None:
            raise KeyError(f"Unknown incident: {incident_id}")
        return [item for item in memory.outcomes if item.result == result]

    def retrieve_failed_actions(self, incident_id: str) -> list[Outcome]:
        return self._outcomes(incident_id, "FAILED")

    def retrieve_successful_actions(self, incident_id: str) -> list[Outcome]:
        return self._outcomes(incident_id, "SUCCESS")

    def store_failed_remediation_chunks(self, chunks: list[FailedRemediationChunk]) -> None:
        for item in chunks:
            chunk = FailedRemediationChunk.model_validate(item.model_dump())
            response = self.transport.call(
                "retain", bank_id=self.bank_id,
                document_id=failed_chunk_document_id(chunk.chunk_id),
                content=chunk.model_dump_json(), retain_async=False,
                context=("Failed or partial remediation evidence. Preserve the action, observed result, "
                         "incident context, and lesson for future incident response."),
                metadata={"incident_id": chunk.incident_id, "outcome_id": chunk.outcome_id,
                          "chunk_id": chunk.chunk_id, "source_filename": chunk.source_filename,
                          "schema": "aii-failed-v1"},
                tags=["aii-v1", "failed-remediation"],
            )
            if not response.success or response.var_async:
                raise HindsightUnavailable("Hindsight did not confirm failed-remediation retention")

    def retrieve_failed_remediation_chunks(self, query: str, limit: int = 10) -> list[FailedRemediationChunk]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("limit must be an integer from 1 to 100")
        response = self.transport.call("recall", bank_id=self.bank_id, query=query,
                                       types=["world", "experience"], budget="mid", max_tokens=4096,
                                       tags=["aii-v1", "failed-remediation"], tags_match="all_strict")
        matches = []
        for key in dict.fromkeys(item.document_id for item in response.results
                                 if item.document_id and item.document_id.startswith("aii-failed-")):
            content = self.transport.call("get_document", bank_id=self.bank_id, document_id=key)
            if content is None:
                raise ValueError("Hindsight recalled a failed-remediation chunk whose source is missing")
            try:
                chunk = FailedRemediationChunk.model_validate_json(content)
            except (ValueError, TypeError):
                raise ValueError("Hindsight source document is not a valid failed-remediation chunk") from None
            if failed_chunk_document_id(chunk.chunk_id) != key:
                raise ValueError("Hindsight failed-remediation document ID does not match its chunk")
            matches.append(chunk)
            if len(matches) == limit:
                break
        return matches
