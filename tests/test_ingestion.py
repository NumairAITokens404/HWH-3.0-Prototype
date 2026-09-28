"""Upload validation, structured chunking, persistence, and search."""

from pathlib import Path
from io import StringIO
from types import SimpleNamespace
import csv
import json
import tempfile
import unittest
from unittest.mock import patch

from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets
from memory.sqlite_client import SQLiteMemoryClient
from services.ingestion_service import (IngestionValidationError, failed_remediation_chunks,
                                        ingest_incident_history, parse_incident_history)


ROOT = Path(__file__).resolve().parents[1]


class IngestionTests(unittest.TestCase):
    def setUp(self):
        _, self.history, _ = load_datasets(ROOT / "data")

    def payload(self, records=None):
        records = records or self.history[:2]
        return ("[" + ",".join(item.model_dump_json() for item in records) + "]").encode()

    def test_ingests_records_and_failed_chunks_idempotently(self):
        client = MockHindsightClient()
        result = ingest_incident_history(self.payload(), "history.json", client, "mock")
        self.assertEqual(result.incident_count, 2)
        self.assertEqual(result.failed_remediation_chunk_count, 2)
        self.assertEqual(result.embedding_status, "NOT_AVAILABLE_LOCAL")
        self.assertEqual(result.stages, ["UPLOADED", "VALIDATED", "CHUNKED", "STORED"])
        ingest_incident_history(self.payload(), "history.json", client, "mock")
        matches = client.retrieve_failed_remediation_chunks("retry underlying cause")
        self.assertEqual(len(matches), 2)
        self.assertTrue(all(item.result == "FAILED" for item in matches))

    def test_preflight_conflict_prevents_partial_record_writes(self):
        client = MockHindsightClient()
        client.store_incident_memory(self.history[1].model_copy(update={"root_cause": "different"}))
        with self.assertRaises(ValueError):
            ingest_incident_history(self.payload(), "history.json", client, "mock")
        self.assertIsNone(client.get_incident_memory(self.history[0].incident.incident_id))

    def test_parser_rejects_bad_shapes_encoding_and_duplicates(self):
        for payload in (b"", b"not-json", b"[]", b'{"records": [], "extra": true}',
                        self.payload([self.history[0], self.history[0]]), b"\xff"):
            with self.subTest(payload=payload[:30]):
                with self.assertRaises(IngestionValidationError):
                    parse_incident_history(payload)

    def test_csv_maps_explicit_columns_into_validated_records(self):
        record = self.history[0]
        stream = StringIO(newline="")
        fields = ["incident_id", "service", "severity", "environment", "symptoms", "error_code",
                  "error_message", "customer_id", "transaction_id", "job_id", "recent_change",
                  "root_cause", "recommendation", "outcomes", "final_resolution", "final_outcome"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "incident_id": record.incident.incident_id, "service": record.incident.service,
            "severity": record.incident.severity, "environment": record.incident.environment,
            "symptoms": "|".join(record.incident.symptoms), "error_code": record.incident.error_code,
            "error_message": record.incident.error_message, "customer_id": record.incident.customer_id,
            "transaction_id": record.incident.transaction_id, "job_id": record.incident.job_id,
            "recent_change": record.incident.recent_change,
            "root_cause": record.root_cause,
            "recommendation": (json.dumps(record.recommendation.model_dump())
                               if record.recommendation is not None else ""),
            "outcomes": json.dumps([item.model_dump() for item in record.outcomes]),
            "final_resolution": record.final_resolution, "final_outcome": record.final_outcome,
        })
        self.assertEqual(parse_incident_history(stream.getvalue().encode(), "history.csv"), [record])

    def test_markdown_log_and_pdf_use_validated_embedded_records(self):
        record = self.history[0]
        block = f"```incident-memory\n{record.model_dump_json()}\n```"
        self.assertEqual(parse_incident_history(block.encode(), "postmortem.md"), [record])
        marked = f"AII_INCIDENT_MEMORY_BEGIN\n{record.model_dump_json()}\nAII_INCIDENT_MEMORY_END"
        self.assertEqual(parse_incident_history(marked.encode(), "incident.log"), [record])
        page = SimpleNamespace(extract_text=lambda: block)
        reader = SimpleNamespace(is_encrypted=False, pages=[page])
        with patch("pypdf.PdfReader", return_value=reader):
            self.assertEqual(parse_incident_history(b"%PDF-test", "postmortem.pdf"), [record])

    def test_unstructured_documents_and_unsupported_formats_are_rejected(self):
        for content, filename in ((b"plain prose", "note.md"), (b"plain log", "incident.log"),
                                  (b"data", "archive.exe")):
            with self.subTest(filename=filename):
                with self.assertRaises(IngestionValidationError):
                    parse_incident_history(content, filename)

    def test_structure_aware_chunks_are_bounded_and_traceable(self):
        record = self.history[0].model_copy(deep=True)
        record.outcomes[0].lesson_learned = "Long failure detail. " * 400
        chunks = failed_remediation_chunks(record, "postmortem.json")
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(item.content) <= 3000 for item in chunks))
        self.assertEqual([item.chunk_index for item in chunks], list(range(len(chunks))))
        self.assertTrue(all(item.incident_id == record.incident.incident_id for item in chunks))

    def test_sqlite_chunks_survive_reopen(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".test-ingestion-") as directory:
            path = Path(directory) / "memory.sqlite3"
            first = SQLiteMemoryClient(path)
            ingest_incident_history(self.payload([self.history[0]]), "history.json", first, "sqlite")
            reopened = SQLiteMemoryClient(path)
            matches = reopened.retrieve_failed_remediation_chunks("retry underlying cause")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].outcome_id, self.history[0].outcomes[0].outcome_id)


if __name__ == "__main__":
    unittest.main()
