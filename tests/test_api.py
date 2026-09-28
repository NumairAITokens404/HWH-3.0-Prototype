"""HTTP contracts, workflow state, validation, and policy boundaries."""

from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from api.app import create_app
from api.runtime import ApiRuntime
from config import Settings


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
        self.assertFalse(capabilities["file_ingestion"])
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/incidents/investigate", paths)
        cors = self.client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                                           "Access-Control-Request-Method": "GET"})
        self.assertEqual(cors.status_code, 200)
        self.assertEqual(cors.headers["access-control-allow-origin"], "http://localhost:5173")

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


if __name__ == "__main__":
    unittest.main()
