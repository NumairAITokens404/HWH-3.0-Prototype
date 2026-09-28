"""Contracts for uploaded history and searchable failed-remediation evidence."""

from hashlib import sha256
from typing import Literal

from pydantic import Field

from schemas.incident import NonEmpty, Schema


class FailedRemediationChunk(Schema):
    chunk_id: NonEmpty
    incident_id: NonEmpty
    outcome_id: NonEmpty
    source_filename: NonEmpty
    action: NonEmpty
    result: Literal["FAILED", "PARTIAL"]
    chunk_index: int = Field(ge=0)
    content: NonEmpty = Field(max_length=3000)

    @classmethod
    def identified(cls, **values):
        identity = "\x1f".join(str(values[key]) for key in
                               ("incident_id", "outcome_id", "source_filename", "chunk_index", "content"))
        return cls(chunk_id="failed-" + sha256(identity.encode()).hexdigest(), **values)


class IngestionResult(Schema):
    status: Literal["COMPLETED"] = "COMPLETED"
    source_filename: NonEmpty
    memory_backend: NonEmpty
    incident_count: int = Field(ge=0)
    failed_remediation_chunk_count: int = Field(ge=0)
    incident_ids: list[NonEmpty]
    embedding_status: Literal["HINDSIGHT_SERVER", "NOT_AVAILABLE_LOCAL"]
    stages: list[Literal["UPLOADED", "VALIDATED", "CHUNKED", "STORED"]]


class FailedRemediationSearchResult(Schema):
    query: NonEmpty
    matches: list[FailedRemediationChunk]
