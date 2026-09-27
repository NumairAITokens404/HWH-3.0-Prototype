"""Phase 1 contract, dataset, and memory behavior checks."""

import json
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from schemas.incident import Incident
from schemas.outcome import IncidentMemory, Outcome
from schemas.remediation import RemediationAction

DATA = Path(__file__).resolve().parents[1] / "data"


class PhaseOneTests(unittest.TestCase):
    def setUp(self):
        self.incidents, self.history, self.cases = load_datasets(DATA)
        self.client = MockHindsightClient()
        seed_memory(self.client, self.history)

    def test_dataset_coverage_and_ordered_attempts(self):
        self.assertEqual(len(self.incidents), 18)
        self.assertEqual(len(self.cases), 6)
        self.assertEqual(len({item.service for item in self.incidents}), 6)
        for record in self.history:
            self.assertEqual([item.result for item in record.outcomes], ["FAILED", "SUCCESS", "SUCCESS"])
            self.assertEqual(record.outcomes[0].action, record.outcomes[-1].action)
            self.assertIsNotNone(record.root_cause)

    def test_retrieves_relevant_history_for_each_family(self):
        for case in self.cases:
            with self.subTest(incident=case.incident.incident_id):
                matches = self.client.retrieve_similar_incidents(case.incident, limit=3)
                self.assertEqual({match.memory.incident.incident_id for match in matches}, set(case.relevant_incident_ids))
                self.assertTrue(all(any(item.result == "FAILED" for item in match.memory.outcomes) for match in matches))

    def test_stores_outcomes_idempotently_and_retrieves_new_memory(self):
        incident = self.cases[0].incident
        self.client.store_incident_memory(IncidentMemory(incident=incident))
        outcome = Outcome(outcome_id="NEW-OUTCOME", incident_id=incident.incident_id,
                          action="retry_request", result="FAILED", risk_level="LOW",
                          verified=True, lesson_learned="Retry alone failed.")
        self.client.store_remediation_outcome(outcome)
        self.client.store_remediation_outcome(outcome)
        self.assertEqual(len(self.client.retrieve_failed_actions(incident.incident_id)), 1)
        query = incident.model_copy(update={"incident_id": "FOLLOW-UP"})
        matches = self.client.retrieve_similar_incidents(query, limit=20)
        stored = next(item.memory for item in matches if item.memory.incident.incident_id == incident.incident_id)
        self.assertEqual(stored.outcomes, [outcome])

    def test_action_filters_keep_both_contexts(self):
        key = self.incidents[0].incident_id
        failed = self.client.retrieve_failed_actions(key)
        successful = self.client.retrieve_successful_actions(key)
        self.assertEqual(len(failed), 1)
        self.assertEqual(len(successful), 2)
        self.assertEqual(failed[0].action, successful[-1].action)

    def test_defensive_copies(self):
        record = self.history[0]
        record.incident.symptoms.append("caller mutation")
        matches = self.client.retrieve_similar_incidents(self.cases[0].incident)
        self.assertTrue(all("caller mutation" not in item.memory.incident.symptoms for item in matches))
        matches[0].memory.outcomes.clear()
        self.assertEqual(len(self.client.retrieve_failed_actions(matches[0].memory.incident.incident_id)), 1)
        outcome = self.client.retrieve_failed_actions(self.incidents[0].incident_id)[0]
        outcome.lesson_learned = "changed by caller"
        self.assertNotEqual(self.client.retrieve_failed_actions(self.incidents[0].incident_id)[0].lesson_learned, outcome.lesson_learned)

    def test_duplicate_conflicts_and_unknown_incidents(self):
        self.client.store_incident_memory(self.history[0])
        record = self.history[0].model_copy(deep=True)
        record.root_cause = "conflicting root cause"
        with self.assertRaises(ValueError):
            self.client.store_incident_memory(record)
        outcome = self.history[0].outcomes[0].model_copy(deep=True)
        outcome.result = "SUCCESS"
        with self.assertRaises(ValueError):
            self.client.store_remediation_outcome(outcome)
        outcome.incident_id = "UNKNOWN"
        with self.assertRaises(KeyError):
            self.client.store_remediation_outcome(outcome)
        with self.assertRaises(KeyError):
            self.client.retrieve_failed_actions("UNKNOWN")

    def test_empty_and_unrelated_retrieval(self):
        self.assertEqual(MockHindsightClient().retrieve_similar_incidents(self.cases[0].incident), [])
        query = Incident(incident_id="UNRELATED", service="unrelated", severity="LOW",
                         symptoms=["unrelated"], environment="production")
        self.assertEqual(self.client.retrieve_similar_incidents(query), [])
        for limit in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                self.client.retrieve_similar_incidents(query, limit=limit)

    def test_self_exclusion_and_deterministic_ranking(self):
        query = self.incidents[0]
        matches = self.client.retrieve_similar_incidents(query)
        self.assertNotIn(query.incident_id, [item.memory.incident.incident_id for item in matches])
        self.assertEqual(matches, self.client.retrieve_similar_incidents(query))
        self.assertEqual([item.score for item in matches], sorted([item.score for item in matches], reverse=True))

    def test_schema_rejects_invalid_data(self):
        incident = self.incidents[0].model_dump()
        for changes in ({"incident_id": " "}, {"symptoms": []}, {"severity": "unknown"}, {"unexpected": True}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                Incident.model_validate(incident | changes)
        action = dict(action_name="retry", description="Retry a mock job", risk_level="LOW", reason="A transient failure", confidence=0.8)
        for changes in ({"confidence": -0.1}, {"confidence": 1.1}, {"confidence": float("nan")}, {"risk_level": "SAFE"}):
            with self.assertRaises(ValidationError):
                RemediationAction.model_validate(action | changes)
        outcome = self.history[0].outcomes[0].model_dump()
        for changes in ({"result": "unknown"}, {"resolution_time_minutes": -1}):
            with self.assertRaises(ValidationError):
                Outcome.model_validate(outcome | changes)

    def test_memory_rejects_mismatched_or_duplicate_outcomes(self):
        record = self.history[0].model_dump()
        record["outcomes"][0]["incident_id"] = "WRONG"
        with self.assertRaises(ValidationError):
            IncidentMemory.model_validate(record)
        record = self.history[0].model_dump()
        record["outcomes"].append(record["outcomes"][0])
        with self.assertRaises(ValidationError):
            IncidentMemory.model_validate(record)

    def test_dataset_loader_rejects_leakage_and_broken_references(self):
        with tempfile.TemporaryDirectory(dir=DATA.parent, prefix=".phase1-test-") as directory:
            root = Path(directory)
            assert root.resolve().is_relative_to(DATA.parent.resolve())
            for source in DATA.glob("*.json"):
                (root / source.name).write_bytes(source.read_bytes())
            cases = json.loads((root / "test_incidents.json").read_text())
            cases[0]["incident"]["incident_id"] = self.incidents[0].incident_id
            (root / "test_incidents.json").write_text(json.dumps(cases))
            with self.assertRaisesRegex(ValueError, "Held-out"):
                load_datasets(root)
            cases[0]["incident"]["incident_id"] = "TEST-001"
            cases[0]["relevant_incident_ids"] = ["MISSING"]
            (root / "test_incidents.json").write_text(json.dumps(cases))
            with self.assertRaisesRegex(ValueError, "unknown historical"):
                load_datasets(root)


if __name__ == "__main__":
    unittest.main()
