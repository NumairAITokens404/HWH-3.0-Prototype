"""HTTP contracts, workflow state, validation, and policy boundaries."""

from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from api.app import create_app
from api.runtime import ApiRuntime
from config import Settings
from memory.memory_writer import load_datasets


ROOT = Path(__file__).resolve().parents[1]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(data_dir=ROOT / "data", api_cors_origins=("http://localhost:5173",))
        self.runtime = ApiRuntime(self.settings)
        self.client = TestClient(create_app(self.settings, self.runtime))

    def test_health_capabilities_and_openapi(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["memory_backend"], "mock")
        self.assertTrue(health.json()["simulated_actions"])
        capabilities = self.client.get("/api/capabilities").json()
        self.assertFalse(capabilities["persistent_memory"])
        self.assertTrue(capabilities["file_ingestion"])
        self.assertEqual(capabilities["embedding_provider"], "none")
        self.assertFalse(capabilities["authenticated_approvals"])
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/incidents/investigate", paths)
        cors = self.client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                                           "Access-Control-Request-Method": "GET"})
        self.assertEqual(cors.status_code, 200)
        self.assertEqual(cors.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_upload_and_search_failed_remediation_memory(self):
        _, history, _ = load_datasets(ROOT / "data")
        record = history[0].model_copy(deep=True)
        record.incident.incident_id = "UPLOADED-001"
        for outcome in record.outcomes:
            outcome.incident_id = "UPLOADED-001"
            outcome.outcome_id = "UPLOADED-" + outcome.outcome_id
        response = self.client.post("/api/memory/uploads",
                                    files={"file": ("history.json", record.model_dump_json(), "application/json")})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["failed_remediation_chunk_count"], 1)
        search = self.client.get("/api/memory/failed-remediations",
                                 params={"q": "retry underlying cause"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["matches"][0]["incident_id"], "UPLOADED-001")

    def test_upload_rejects_bad_type_payload_size_and_conflict(self):
        self.assertEqual(self.client.post("/api/memory/uploads",
                                         files={"file": ("history.exe", "{}", "application/octet-stream")}).status_code, 415)
        self.assertEqual(self.client.post("/api/memory/uploads",
                                         files={"file": ("history.txt", "plain text", "text/plain")}).status_code, 422)
        self.assertEqual(self.client.post("/api/memory/uploads",
                                         files={"file": ("history.json", "bad", "application/json")}).status_code, 422)
        small_settings = Settings(data_dir=ROOT / "data", api_upload_max_bytes=1024)
        small = TestClient(create_app(small_settings, ApiRuntime(small_settings)))
        self.assertEqual(small.post("/api/memory/uploads",
                                   files={"file": ("large.json", b"x" * 1025, "application/json")}).status_code, 413)
        _, history, _ = load_datasets(ROOT / "data")
        changed = history[0].model_copy(update={"root_cause": "conflicting cause"})
        conflict = self.client.post("/api/memory/uploads",
                                    files={"file": ("history.json", changed.model_dump_json(), "application/json")})
        self.assertEqual(conflict.status_code, 409)

    def test_investigation_is_read_only_and_structured(self):
        incident = self.runtime.cases[0].incident.model_copy(update={"incident_id": "API-INVESTIGATE"})
        response = self.client.post("/api/incidents/investigate", json=incident.model_dump())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recommended_action"]["action_name"], "reset_customer_pin")
        self.assertIsNone(self.runtime.memory.get_incident_memory("API-INVESTIGATE"))

    def test_invalid_incident_is_rejected(self):
        response = self.client.post("/api/incidents/investigate", json={"incident_id": "bad"})
        self.assertEqual(response.status_code, 422)

    def test_low_risk_and_partial_demo_workflows(self):
        success = self.client.post("/api/demo/workflows", json={"scenario": "low-risk-success"})
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["status"], "SUCCESS")
        self.assertTrue(success.json()["memory_stored"])
        partial = self.client.post("/api/demo/workflows", json={"scenario": "partial-recovery"})
        self.assertEqual(partial.status_code, 200)
        self.assertEqual(partial.json()["status"], "PARTIAL")
        self.assertEqual(partial.json()["reprocessing"]["result"], "FAILED")

    def test_high_risk_requires_bound_approval(self):
        started = self.client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"})
        body = started.json()
        self.assertEqual(body["status"], "HUMAN_APPROVAL_REQUIRED")
        self.assertIsNone(body["remediation"])
        path = f"/api/demo/workflows/{body['incident_id']}/approval"
        wrong = self.client.post(path, json={"request_id": "wrong", "approved": True, "reviewer": "operator"})
        self.assertEqual(wrong.status_code, 200)
        self.assertEqual(wrong.json()["status"], "BLOCKED")
        approved = self.client.post(path, json={"request_id": body["decision"]["request_id"],
                                                "approved": True, "reviewer": "operator"})
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "SUCCESS")
        self.assertTrue(approved.json()["memory_stored"])
        self.assertEqual(self.client.post(path, json={"request_id": body["decision"]["request_id"],
                                                      "approved": True, "reviewer": "operator"}).status_code, 404)

    def test_denial_is_terminal(self):
        body = self.client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"}).json()
        path = f"/api/demo/workflows/{body['incident_id']}/approval"
        denied = self.client.post(path, json={"request_id": body["decision"]["request_id"],
                                              "approved": False, "reviewer": "operator"})
        self.assertEqual(denied.json()["status"], "DENIED")
        self.assertEqual(self.client.post(path, json={"request_id": body["decision"]["request_id"],
                                                      "approved": True, "reviewer": "operator"}).status_code, 404)

    def test_authenticated_approval_derives_reviewer_from_bearer_token(self):
        settings = Settings(data_dir=ROOT / "data", approval_credentials=(("alice", "secret-token"),))
        runtime = ApiRuntime(settings)
        client = TestClient(create_app(settings, runtime))
        self.assertTrue(client.get("/api/capabilities").json()["authenticated_approvals"])
        body = client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"}).json()
        path = f"/api/demo/workflows/{body['incident_id']}/approval"
        payload = {"request_id": body["decision"]["request_id"], "approved": True}
        self.assertEqual(client.post(path, json=payload).status_code, 401)
        self.assertEqual(client.post(path, json=payload,
                                     headers={"Authorization": "Bearer wrong"}).status_code, 401)
        approved = client.post(path, json=payload,
                               headers={"Authorization": "Bearer secret-token"})
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["approval"]["reviewer"], "alice")
        events = runtime.workflow_store.events_for(body["incident_id"])
        submitted = next(event for event in events if event.event_type == "APPROVAL_SUBMITTED")
        self.assertEqual(submitted.details["reviewer"], "alice")

    def test_authenticated_approval_rejects_spoofed_reviewer(self):
        settings = Settings(data_dir=ROOT / "data", approval_credentials=(("alice", "secret-token"),))
        runtime = ApiRuntime(settings)
        client = TestClient(create_app(settings, runtime))
        body = client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"}).json()
        response = client.post(f"/api/demo/workflows/{body['incident_id']}/approval",
                               json={"request_id": body["decision"]["request_id"], "approved": True,
                                     "reviewer": "admin"},
                               headers={"Authorization": "Bearer secret-token"})
        self.assertEqual(response.status_code, 401)

    def test_unknown_workflow_and_scenario_are_rejected(self):
        missing = self.client.post("/api/demo/workflows/missing/approval",
                                   json={"request_id": "x", "approved": True, "reviewer": "operator"})
        self.assertEqual(missing.status_code, 404)
        invalid = self.client.post("/api/demo/workflows", json={"scenario": "invented"})
        self.assertEqual(invalid.status_code, 422)

    def test_runtime_capacity_is_bounded(self):
        runtime = ApiRuntime(self.settings, max_active_runs=1)
        client = TestClient(create_app(self.settings, runtime))
        self.assertEqual(client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"}).status_code, 200)
        response = client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"})
        self.assertEqual(response.status_code, 503)

    def test_ui_contract_supports_live_frontend_workflow(self):
        incidents = self.client.get("/api/ui/incidents")
        self.assertEqual(incidents.status_code, 200)
        self.assertEqual(len(incidents.json()), 6)
        detail = self.client.get("/api/ui/incidents/TEST-001")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["investigation"]["status"], "RECOMMENDATION_READY")
        completed = self.client.post("/api/ui/incidents/TEST-001/workflow")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "SUCCESS")
        overview = self.client.get("/api/ui/overview").json()
        self.assertEqual(overview["resolved"], 1)
        self.assertEqual(overview["memoryRecords"], 19)

    def test_ui_high_risk_workflow_resumes_with_approval(self):
        pending = self.client.post("/api/ui/incidents/TEST-003/workflow").json()
        self.assertEqual(pending["status"], "HUMAN_APPROVAL_REQUIRED")
        approved = self.client.post("/api/ui/incidents/TEST-003/approval", json={
            "request_id": pending["decision"]["request_id"], "approved": True, "reviewer": "operator",
        })
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "SUCCESS")

    def test_ui_memory_and_evaluation_are_live(self):
        memory = self.client.get("/api/ui/memory", params={"service": "queue-service", "result": "FAILED"})
        self.assertEqual(memory.status_code, 200)
        self.assertEqual(len(memory.json()), 3)
        evaluation = self.client.get("/api/ui/evaluation")
        self.assertEqual(evaluation.status_code, 200)
        self.assertTrue(evaluation.json()["metrics"])


if __name__ == "__main__":
    unittest.main()
