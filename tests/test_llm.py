"""Model contracts, evidence guards, fallback, and policy boundaries."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from config import Settings
from llm.client import LLMError, OllamaClient
from llm.prompts import investigation_messages
from agents.remediation_memory import RemediationMemory
from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from schemas.llm import LLMProposal
from services.incident_service import investigate_incident, IncidentWorkflow
from schemas.workflow import SimulationScenario
from tools.simulation import SimulationWorld


class StubLLM:
    model = "test-model"

    def __init__(self, proposal=None, error=None):
        self.proposal, self.error = proposal, error
        self.messages = None

    def generate(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.proposal


class LLMTests(unittest.TestCase):
    def setUp(self):
        _, self.history, self.cases = load_datasets(Path(__file__).resolve().parents[1] / "data")
        self.memory = MockHindsightClient()
        seed_memory(self.memory, self.history)
        self.incident = self.cases[0].incident
        self.proposal = LLMProposal(status="RECOMMEND", action_name="reset_customer_pin",
                                   likely_root_cause="A stale PIN state", explanation="Reset state before retrying, as in INC-101.",
                                   evidence_ids=["INC-101"], confidence=0.8)

    def test_grounded_proposal_and_canonical_fields(self):
        result = investigate_incident(self.incident, self.memory, StubLLM(self.proposal))
        self.assertEqual(result.method, "llm_grounded")
        self.assertEqual(result.recommended_action.action_name, "reset_customer_pin")
        self.assertEqual(result.likely_root_cause, "stale PIN master data")
        self.assertFalse(result.execution_authorized)
        self.assertEqual(result.model_proposal.confidence, 0.8)
        self.assertNotEqual(result.recommended_action.confidence, 0.8)

    def test_grounded_outcome_citations_are_accepted(self):
        proposal = self.proposal.model_copy(update={"evidence_ids": ["OUT-101-2", "OUT-101-3"]})
        result = investigate_incident(self.incident, self.memory, StubLLM(proposal))
        self.assertEqual(result.method, "llm_grounded")
        self.assertEqual(result.recommended_action.action_name, "reset_customer_pin")

    def test_unknown_citation_falls_back_visibly(self):
        self.proposal.evidence_ids = ["FABRICATED"]
        result = investigate_incident(self.incident, self.memory, StubLLM(self.proposal))
        self.assertEqual(result.method, "deterministic_fallback")
        self.assertEqual(result.fallback_reason, "unknown_evidence_reference")

    def test_no_history_is_advisory_and_does_not_execute(self):
        self.proposal.evidence_ids = []
        result = investigate_incident(self.incident, MockHindsightClient(), StubLLM(self.proposal))
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result.recommended_action)
        self.assertEqual(result.model_proposal.action_name, "reset_customer_pin")

    def test_wrong_action_and_uncited_action_are_rejected(self):
        for changes in ({"action_name": "delete_database"}, {"evidence_ids": []}, {"action_name": "reprocess_transaction"}):
            result = investigate_incident(self.incident, self.memory, StubLLM(self.proposal.model_copy(update=changes)))
            self.assertIsNone(result.recommended_action)

    def test_model_abstention_is_respected(self):
        abstain = self.proposal.model_copy(update={"status": "ABSTAIN", "action_name": None})
        result = investigate_incident(self.incident, self.memory, StubLLM(abstain))
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result.recommended_action)

    def test_connection_error_uses_disclosed_baseline(self):
        result = investigate_incident(self.incident, self.memory, StubLLM(error=LLMError("timeout")))
        self.assertEqual(result.method, "deterministic_fallback")
        self.assertEqual(result.fallback_reason, "timeout")
        self.assertEqual(result.recommended_action.action_name, "reset_customer_pin")

    def test_high_risk_llm_recommendation_still_waits_for_approval(self):
        incident = self.cases[2].incident
        proposal = self.proposal.model_copy(update={"action_name": "rollback_connection_pool_change", "evidence_ids": ["INC-107"]})
        world = SimulationWorld([SimulationScenario(incident=incident, operation_id="TEST", required_action="rollback_connection_pool_change")])
        result = IncidentWorkflow(self.memory, world, StubLLM(proposal)).run(incident)
        self.assertEqual(result.status, "HUMAN_APPROVAL_REQUIRED")
        self.assertEqual(world.observe(incident), (False, False))

    def test_prompt_has_no_evaluation_labels_or_baseline_answer(self):
        messages = investigation_messages(self.incident, RemediationMemory(self.memory).analyze(self.incident))
        payload = json.loads(messages[1]["content"])
        self.assertEqual(set(payload), {"incident", "historical_evidence", "verified_action_counts", "allowed_evidence_ids"})
        self.assertNotIn("expected_action", json.dumps(payload))
        self.assertIn("untrusted data", messages[0]["content"])
        self.assertIn("OUT-101-2", payload["allowed_evidence_ids"])

    def test_schema_rejects_authorization_and_bad_confidence(self):
        from pydantic import ValidationError
        for change in ({"execution_authorized": True}, {"confidence": 2}, {"status": "ABSTAIN"}):
            with self.assertRaises(ValidationError):
                LLMProposal.model_validate(self.proposal.model_dump() | change)

    def test_ollama_request_uses_schema_and_bounded_generation(self):
        client = OllamaClient(Settings(data_dir=Path("data")))
        response = {"done": True, "message": {"content": self.proposal.model_dump_json()}}
        with patch.object(client, "_request", return_value=response) as request:
            self.assertEqual(client.generate([{"role": "user", "content": "test"}]), self.proposal)
        payload = request.call_args.args[1]
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_ctx"], 8192)
        self.assertEqual(payload["format"]["additionalProperties"], False)

    def test_incomplete_or_malformed_output_is_error(self):
        client = OllamaClient(Settings(data_dir=Path("data")))
        for response in ({"done": False}, {"done": True, "done_reason": "length"}, {"done": True, "message": {"content": "bad"}}):
            with patch.object(client, "_request", return_value=response):
                with self.assertRaises(LLMError):
                    client.generate([{"role": "user", "content": "test"}])

    def test_prompt_over_budget_fails_before_request(self):
        client = OllamaClient(Settings(data_dir=Path("data")))
        with patch.object(client, "_request") as request:
            with self.assertRaises(LLMError):
                client.generate([{"role": "user", "content": "x" * 30000}])
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
