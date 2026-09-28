"""Validate uploaded incident history and retain structured failure evidence."""

import json
from pydantic import ValidationError

from memory.hindsight_client import HindsightClient
from schemas.ingestion import FailedRemediationChunk, IngestionResult
from schemas.outcome import IncidentMemory


class IngestionValidationError(ValueError):
    """The uploaded document is not an accepted incident-history payload."""


def _records(payload) -> list[IncidentMemory]:
    if isinstance(payload, dict) and "records" in payload:
        if set(payload) != {"records"}:
            raise IngestionValidationError("A records wrapper cannot contain additional fields")
        payload = payload["records"]
    elif isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        raise IngestionValidationError("Upload one incident-memory object or a non-empty JSON array")
    if len(payload) > 500:
        raise IngestionValidationError("An upload may contain at most 500 incident records")
    try:
        records = [IncidentMemory.model_validate(item) for item in payload]
    except (ValidationError, TypeError, ValueError) as exc:
        raise IngestionValidationError("Upload does not match the IncidentMemory schema") from exc
    ids = [item.incident.incident_id for item in records]
    if len(ids) != len(set(ids)):
        raise IngestionValidationError("Incident IDs must be unique within an upload")
    return records


def parse_incident_history(content: bytes) -> list[IncidentMemory]:
    if not content:
        raise IngestionValidationError("Uploaded file is empty")
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IngestionValidationError("Upload must be valid UTF-8 JSON") from exc
    return _records(payload)


def _split(content: str, maximum: int = 2400, overlap: int = 200) -> list[str]:
    if maximum < 500 or overlap < 0 or overlap >= maximum:
        raise ValueError("Invalid chunking configuration")
    chunks, start = [], 0
    while start < len(content):
        end = min(len(content), start + maximum)
        if end < len(content):
            candidates = [content.rfind("\n", start + maximum // 2, end),
                          content.rfind(". ", start + maximum // 2, end)]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + 1
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(content):
            break
        start = max(start + 1, end - overlap)
    return chunks


def failed_remediation_chunks(memory: IncidentMemory, source_filename: str) -> list[FailedRemediationChunk]:
    incident = memory.incident
    chunks = []
    for outcome in memory.outcomes:
        if outcome.result not in {"FAILED", "PARTIAL"}:
            continue
        text = "\n".join([
            f"Incident: {incident.incident_id}",
            f"Service: {incident.service}",
            f"Environment: {incident.environment}",
            f"Severity: {incident.severity}",
            f"Error code: {incident.error_code or 'unknown'}",
            f"Symptoms: {'; '.join(incident.symptoms)}",
            f"Root-cause hypothesis: {memory.root_cause or 'unknown'}",
            f"Failed remediation action: {outcome.action}",
            f"Observed result: {outcome.result}",
            f"Verified: {outcome.verified}",
            f"Lesson: {outcome.lesson_learned}",
            f"Final incident outcome: {memory.final_outcome or 'unknown'}",
        ])
        for index, content in enumerate(_split(text)):
            chunks.append(FailedRemediationChunk.identified(
                incident_id=incident.incident_id, outcome_id=outcome.outcome_id,
                source_filename=source_filename, action=outcome.action,
                result=outcome.result, chunk_index=index, content=content,
            ))
    return chunks


def ingest_incident_history(content: bytes, filename: str, client: HindsightClient,
                            memory_backend: str) -> IngestionResult:
    source_filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not source_filename:
        raise IngestionValidationError("A source filename is required")
    records = parse_incident_history(content)
    for record in records:
        existing = client.get_incident_memory(record.incident.incident_id)
        if existing is not None and existing != record:
            raise ValueError(f"Incident {record.incident.incident_id} already exists with different content")
    chunks = [chunk for record in records for chunk in failed_remediation_chunks(record, source_filename)]
    for record in records:
        client.store_incident_memory(record)
    client.store_failed_remediation_chunks(chunks)
    return IngestionResult(
        source_filename=source_filename, memory_backend=memory_backend,
        incident_count=len(records), failed_remediation_chunk_count=len(chunks),
        incident_ids=[item.incident.incident_id for item in records],
        embedding_status="HINDSIGHT_SERVER" if memory_backend == "hindsight" else "NOT_AVAILABLE_LOCAL",
        stages=["UPLOADED", "VALIDATED", "CHUNKED", "STORED"],
    )
