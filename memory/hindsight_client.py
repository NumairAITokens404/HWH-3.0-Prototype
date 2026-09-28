"""Application-owned interface and offline mock, not Hindsight SDK methods.

The real SDK adapter lives in hindsight_adapter.py. This module's mock remains
offline and uses deterministic lexical scoring.
"""

import re
from typing import Protocol

from pydantic import Field

from schemas.incident import Incident, Schema
from schemas.ingestion import FailedRemediationChunk
from schemas.outcome import IncidentMemory, Outcome


class MemoryMatch(Schema):
    memory: IncidentMemory
    score: float = Field(ge=0, le=1)


class HindsightClient(Protocol):
    def get_incident_memory(self, incident_id: str) -> IncidentMemory | None: ...
    def store_incident_memory(self, memory: IncidentMemory) -> None: ...
    def retrieve_similar_incidents(self, incident: Incident, limit: int = 5) -> list[MemoryMatch]: ...
    def store_remediation_outcome(self, outcome: Outcome) -> None: ...
    def retrieve_failed_actions(self, incident_id: str) -> list[Outcome]: ...
    def retrieve_successful_actions(self, incident_id: str) -> list[Outcome]: ...
    def store_failed_remediation_chunks(self, chunks: list[FailedRemediationChunk]) -> None: ...
    def retrieve_failed_remediation_chunks(self, query: str, limit: int = 10) -> list[FailedRemediationChunk]: ...


def _tokens(incident: Incident) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", " ".join(incident.symptoms).casefold()))


class MockHindsightClient:
    """In-memory store with deterministic lexical retrieval and defensive copies.

    Repeating an identical write is idempotent; conflicting IDs are rejected.
    Outcomes are appended in write order and retained for the process lifetime.
    """

    def __init__(self):
        self._memories: dict[str, IncidentMemory] = {}
        self._failed_chunks: dict[str, FailedRemediationChunk] = {}

    def get_incident_memory(self, incident_id: str) -> IncidentMemory | None:
        memory = self._memories.get(incident_id)
        return memory.model_copy(deep=True) if memory is not None else None

    def store_incident_memory(self, memory: IncidentMemory) -> None:
        memory = IncidentMemory.model_validate(memory.model_dump())
        key = memory.incident.incident_id
        if key in self._memories and self._memories[key] != memory:
            raise ValueError(f"Incident {key} already exists with different content")
        self._memories[key] = memory.model_copy(deep=True)

    def store_remediation_outcome(self, outcome: Outcome) -> None:
        outcome = Outcome.model_validate(outcome.model_dump())
        memory = self._memories.get(outcome.incident_id)
        if memory is None:
            raise KeyError(f"Unknown incident: {outcome.incident_id}")
        for existing in memory.outcomes:
            if existing.outcome_id == outcome.outcome_id:
                if existing != outcome:
                    raise ValueError(f"Conflicting outcome: {outcome.outcome_id}")
                return
        memory.outcomes.append(outcome.model_copy(deep=True))

    def retrieve_similar_incidents(self, incident: Incident, limit: int = 5) -> list[MemoryMatch]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        matches = []
        query_tokens = _tokens(incident)
        for memory in self._memories.values():
            past = memory.incident
            if past.incident_id == incident.incident_id:
                continue
            same_service = past.service.casefold() == incident.service.casefold()
            same_error = bool(incident.error_code and past.error_code
                              and past.error_code.casefold() == incident.error_code.casefold())
            past_tokens = _tokens(past)
            overlap = len(query_tokens & past_tokens) / max(1, len(query_tokens | past_tokens))
            if not (same_service or same_error or overlap):
                continue
            score = (0.4 * same_service + 0.3 * same_error + 0.2 * overlap
                     + 0.1 * (past.environment.casefold() == incident.environment.casefold()))
            matches.append(MemoryMatch(memory=memory.model_copy(deep=True), score=round(score, 6)))
        return sorted(matches, key=lambda match: (-match.score, match.memory.incident.incident_id))[:limit]

    def _outcomes(self, incident_id: str, result: str) -> list[Outcome]:
        if incident_id not in self._memories:
            raise KeyError(f"Unknown incident: {incident_id}")
        return [item.model_copy(deep=True) for item in self._memories[incident_id].outcomes
                if item.result == result]

    def retrieve_failed_actions(self, incident_id: str) -> list[Outcome]:
        return self._outcomes(incident_id, "FAILED")

    def retrieve_successful_actions(self, incident_id: str) -> list[Outcome]:
        return self._outcomes(incident_id, "SUCCESS")

    def store_failed_remediation_chunks(self, chunks: list[FailedRemediationChunk]) -> None:
        for chunk in chunks:
            chunk = FailedRemediationChunk.model_validate(chunk.model_dump())
            existing = self._failed_chunks.get(chunk.chunk_id)
            if existing is not None and existing != chunk:
                raise ValueError(f"Conflicting failed-remediation chunk: {chunk.chunk_id}")
            self._failed_chunks[chunk.chunk_id] = chunk.model_copy(deep=True)

    def retrieve_failed_remediation_chunks(self, query: str, limit: int = 10) -> list[FailedRemediationChunk]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("limit must be an integer from 1 to 100")
        query_tokens = set(re.findall(r"[a-z0-9]+", query.casefold()))
        ranked = []
        for chunk in self._failed_chunks.values():
            tokens = set(re.findall(r"[a-z0-9]+", chunk.content.casefold()))
            score = len(query_tokens & tokens) / max(1, len(query_tokens | tokens))
            if score:
                ranked.append((score, chunk.chunk_id, chunk))
        return [item[2].model_copy(deep=True) for item in sorted(ranked, key=lambda item: (-item[0], item[1]))[:limit]]
