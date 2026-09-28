"""Offline contract tests; these do not claim live Hindsight verification."""

from pathlib import Path
from types import SimpleNamespace
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from config import Settings
from memory.factory import create_memory_client
from memory.hindsight_adapter import (HindsightMemoryClient, HindsightUnavailable, SDKTransport,
                                      document_id, failed_chunk_document_id)
from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets
from services.ingestion_service import failed_remediation_chunks


class FakeTransport:
    def __init__(self):
        self.documents = {}
        self.retains = 0

    def call(self, operation, **kwargs):
        if operation == "version":
            return SimpleNamespace(api_version="test")
        if operation == "get_document":
            return self.documents.get((kwargs["bank_id"], kwargs["document_id"]))
        if operation == "retain":
            assert kwargs["retain_async"] is False
            self.retains += 1
            self.documents[kwargs["bank_id"], kwargs["document_id"]] = kwargs["content"]
            return SimpleNamespace(success=True, var_async=False)
        if operation == "recall":
            return SimpleNamespace(results=[SimpleNamespace(document_id=key)
                                            for bank, key in self.documents if bank == kwargs["bank_id"]])
        raise AssertionError(operation)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(data_dir=Path("data"), memory_backend="hindsight")
        _, records, cases = load_datasets(Path(__file__).resolve().parents[1] / "data")
        self.record, self.query = records[0], cases[0].incident
        self.transport = FakeTransport()
        self.client = HindsightMemoryClient(self.settings, self.transport)

    def test_roundtrip_and_reopen_preserve_order(self):
        self.client.store_incident_memory(self.record)
        reopened = HindsightMemoryClient(self.settings, self.transport)
        self.assertEqual(reopened.get_incident_memory(self.record.incident.incident_id), self.record)
        self.assertEqual(reopened.retrieve_similar_incidents(self.query)[0].memory, self.record)

    def test_idempotence_and_conflict(self):
        self.client.store_incident_memory(self.record)
        self.client.store_incident_memory(self.record)
        self.assertEqual(self.transport.retains, 1)
        changed = self.record.model_copy(update={"root_cause": "other"})
        with self.assertRaises(ValueError):
            self.client.store_incident_memory(changed)

    def test_appends_outcome_without_losing_history(self):
        self.client.store_incident_memory(self.record)
        outcome = self.record.outcomes[0].model_copy(update={"outcome_id": "NEW"})
        self.client.store_remediation_outcome(outcome)
        self.client.store_remediation_outcome(outcome)
        self.assertEqual(len(self.client.get_incident_memory(outcome.incident_id).outcomes), 4)
        self.assertEqual(len(self.client.retrieve_failed_actions(outcome.incident_id)), 2)
        self.assertEqual(len(self.client.retrieve_successful_actions(outcome.incident_id)), 2)
        with self.assertRaises(ValueError):
            self.client.store_remediation_outcome(outcome.model_copy(update={"result": "SUCCESS"}))

    def test_unknown_incident_and_invalid_limit(self):
        self.assertIsNone(self.client.get_incident_memory("missing"))
        with self.assertRaises(KeyError):
            self.client.store_remediation_outcome(self.record.outcomes[0])
        for limit in (0, True, 1.2):
            with self.assertRaises(ValueError):
                self.client.retrieve_similar_incidents(self.query, limit)

    def test_malformed_or_mismatched_document_fails(self):
        key = (self.settings.hindsight_bank_id, document_id("WRONG"))
        for text in ("not json", self.record.model_dump_json()):
            self.transport.documents[key] = text
            with self.assertRaises(ValueError):
                self.client.get_incident_memory("WRONG")

    def test_document_ids_are_safe_and_bank_isolation_holds(self):
        self.assertRegex(document_id("../a/b"), r"^aii-[0-9a-f]{64}$")
        self.client.store_incident_memory(self.record)
        other = HindsightMemoryClient(Settings(data_dir=Path("data"), hindsight_bank_id="other"), self.transport)
        self.assertEqual(other.retrieve_similar_incidents(self.query), [])

    def test_failed_chunks_are_retained_separately_and_searchable(self):
        chunks = failed_remediation_chunks(self.record, "history.json")
        self.client.store_failed_remediation_chunks(chunks)
        self.assertRegex(failed_chunk_document_id(chunks[0].chunk_id), r"^aii-failed-[0-9a-f]{64}$")
        self.assertEqual(self.client.retrieve_failed_remediation_chunks("retry failure"), chunks)
        # Failed-remediation documents must never be parsed as complete incident records.
        self.client.store_incident_memory(self.record)
        self.assertEqual(self.client.retrieve_similar_incidents(self.query)[0].memory, self.record)

    def test_missing_recalled_document_fails(self):
        with patch.object(self.transport, "call", side_effect=[SimpleNamespace(results=[SimpleNamespace(document_id="aii-missing")]), None]):
            with self.assertRaises(ValueError):
                self.client.retrieve_similar_incidents(self.query)

    def test_configuration_and_factory(self):
        self.assertIsInstance(create_memory_client(Settings(data_dir=Path("data"))), MockHindsightClient)
        self.assertIsInstance(create_memory_client(self.settings), HindsightMemoryClient)
        for overrides in ({"memory_backend": "unknown"}, {"hindsight_timeout": float("nan")},
                          {"hindsight_bank_id": " "}, {"hindsight_base_url": "https://user:secret@example.com"}):
            with self.assertRaises(ValueError):
                Settings(data_dir=Path("data"), **overrides)
        self.assertNotIn("secret", repr(Settings(data_dir=Path("data"), hindsight_api_key="secret")))

    def test_failed_or_async_retention_is_not_success(self):
        for response in (SimpleNamespace(success=False, var_async=False), SimpleNamespace(success=True, var_async=True)):
            with patch.object(self.transport, "call", side_effect=[None, response]):
                with self.assertRaises(HindsightUnavailable):
                    self.client.store_incident_memory(self.record)


class SDKContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import hindsight_client
        except ImportError:
            raise unittest.SkipTest("Optional SDK not installed")

    def test_sdk_document_read_and_cleanup(self):
        sdk = SimpleNamespace(documents=SimpleNamespace(get_document=AsyncMock(return_value=SimpleNamespace(original_text="{}"))), aclose=AsyncMock())
        with patch("hindsight_client.Hindsight", return_value=sdk):
            result = SDKTransport(Settings(data_dir=Path("data"))).call("get_document", bank_id="b", document_id="d")
        self.assertEqual(result, "{}")
        sdk.documents.get_document.assert_awaited_once_with(bank_id="b", document_id="d", _request_timeout=120.0)
        sdk.aclose.assert_awaited_once()

    def test_sdk_call_works_inside_running_event_loop(self):
        sdk = SimpleNamespace(documents=SimpleNamespace(get_document=AsyncMock(return_value=SimpleNamespace(original_text="{}"))), aclose=AsyncMock())

        async def invoke():
            with patch("hindsight_client.Hindsight", return_value=sdk):
                return SDKTransport(Settings(data_dir=Path("data"))).call("get_document", bank_id="b", document_id="d")

        result = asyncio.run(invoke())
        self.assertEqual(result, "{}")
        sdk.aclose.assert_awaited_once()

    def test_sdk_only_404_is_absence_and_errors_are_sanitized(self):
        from hindsight_client_api.exceptions import ApiException
        for status in (404, 401, 500):
            sdk = SimpleNamespace(documents=SimpleNamespace(get_document=AsyncMock(side_effect=ApiException(status=status, reason="secret"))), aclose=AsyncMock())
            with patch("hindsight_client.Hindsight", return_value=sdk):
                transport = SDKTransport(Settings(data_dir=Path("data")))
                if status == 404:
                    self.assertIsNone(transport.call("get_document", bank_id="b", document_id="d"))
                else:
                    with self.assertRaises(HindsightUnavailable) as caught:
                        transport.call("get_document", bank_id="b", document_id="d")
                    self.assertNotIn("secret", str(caught.exception))

    def test_recall_of_new_bank_is_empty_but_other_404_is_an_error(self):
        from hindsight_client_api.exceptions import ApiException
        for body, empty in (("{\"detail\":\"Bank 'new' not found\"}", True), ("Not Found", False)):
            error = ApiException(status=404)
            error.body = body
            sdk = SimpleNamespace(arecall=AsyncMock(side_effect=error), aclose=AsyncMock())
            with patch("hindsight_client.Hindsight", return_value=sdk):
                transport = SDKTransport(Settings(data_dir=Path("data")))
                if empty:
                    self.assertEqual(transport.call("recall", bank_id="new", query="history").results, [])
                else:
                    with self.assertRaises(HindsightUnavailable):
                        transport.call("recall", bank_id="new", query="history")

    def test_missing_original_text_is_not_absence(self):
        sdk = SimpleNamespace(documents=SimpleNamespace(get_document=AsyncMock(return_value=SimpleNamespace(original_text=None))), aclose=AsyncMock())
        with patch("hindsight_client.Hindsight", return_value=sdk):
            with self.assertRaises(HindsightUnavailable):
                SDKTransport(Settings(data_dir=Path("data"))).call("get_document", bank_id="b", document_id="d")


if __name__ == "__main__":
    unittest.main()
