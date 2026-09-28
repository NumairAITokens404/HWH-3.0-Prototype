"""Upload validation, structured chunking, persistence, and search."""

from pathlib import Path
import tempfile
import unittest

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
