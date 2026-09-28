"""Local persistence, dotenv precedence, and reproducible evaluation."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from config import Settings
from evaluation.evaluate_memory import evaluate
from evaluation.metrics import token_f1
from memory.memory_writer import load_datasets
from memory.sqlite_client import SQLiteMemoryClient

ROOT = Path(__file__).resolve().parents[1]


class LocalRuntimeTests(unittest.TestCase):
    def test_sqlite_reopen_idempotence_conflict_and_outcomes(self):
        _, history, cases = load_datasets(ROOT / "data")
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".test-sqlite-") as directory:
            path = Path(directory) / "memory.sqlite3"
            first = SQLiteMemoryClient(path)
            first.store_incident_memory(history[0])
            first.store_incident_memory(history[0])
            reopened = SQLiteMemoryClient(path)
            self.assertEqual(reopened.get_incident_memory("INC-101"), history[0])
            self.assertEqual(reopened.retrieve_similar_incidents(cases[0].incident)[0].memory, history[0])
            with self.assertRaises(ValueError):
                reopened.store_incident_memory(history[0].model_copy(update={"root_cause": "changed"}))
            extra = history[0].outcomes[0].model_copy(update={"outcome_id": "EXTRA"})
            reopened.store_remediation_outcome(extra)
            reopened.store_remediation_outcome(extra)
            self.assertEqual(len(reopened.retrieve_failed_actions("INC-101")), 2)
            with self.assertRaises(ValueError):
                reopened.store_remediation_outcome(extra.model_copy(update={"result": "SUCCESS"}))
            with self.assertRaises(KeyError):
                reopened.retrieve_failed_actions("UNKNOWN")

    def test_dotenv_is_loaded_without_overriding_shell_or_mutating_environment(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".test-env-") as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("LLM_PROVIDER=ollama\nLLM_MODEL=qwen3.5:9b\nMEMORY_BACKEND=sqlite\n", encoding="utf-8")
            with patch.dict(os.environ, {"LLM_MODEL": "override"}, clear=True):
                settings = Settings.from_env(env_file)
                self.assertEqual(settings.llm_provider, "ollama")
                self.assertEqual(settings.llm_model, "override")
                self.assertEqual(settings.memory_backend, "sqlite")
                self.assertNotIn("LLM_PROVIDER", os.environ)

    def test_api_origins_are_parsed_and_validated(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".test-env-") as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("API_CORS_ORIGINS=https://console.example.com,http://localhost:3000\n",
                                encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.from_env(env_file)
            self.assertEqual(settings.api_cors_origins,
                             ("https://console.example.com", "http://localhost:3000"))
        for origin in ("file:///tmp/ui", "https://user:secret@example.com", "https://example.com/path"):
            with self.assertRaises(ValueError):
                Settings(data_dir=ROOT / "data", api_cors_origins=(origin,))

    def test_rules_evaluation_isolated_and_metrics_are_real_counts(self):
        report = evaluate(Settings(data_dir=ROOT / "data"))
        empty = report["variants"]["without_memory"]["metrics"]
        history = report["variants"]["with_memory"]["metrics"]
        self.assertEqual(empty["accepted_action_accuracy"], 0)
        self.assertIsNone(empty["repeated_failed_action_rate_among_proposals"])
        self.assertEqual(history["accepted_action_accuracy"], 1)
        self.assertEqual(history["retrieval_recall"], 2 / 3)
        self.assertEqual(history["simulated_tool_calls_total"], 4)
        self.assertEqual(history["approval_pauses"], 4)
        self.assertTrue(all(item["passed"] for item in report["challenges"]))

    def test_token_f1_handles_missing_and_paraphrased_text(self):
        self.assertEqual(token_f1(None, "stale state"), 0)
        self.assertEqual(token_f1("stale state", "stale state"), 1)
        self.assertAlmostEqual(token_f1("stale cache", "stale state"), 0.5)


if __name__ == "__main__":
    unittest.main()
