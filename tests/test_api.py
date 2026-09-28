"""HTTP contracts, workflow state, validation, and policy boundaries."""

from pathlib import Path
import tempfile
import time
import unittest
import random
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from api.runtime import ApiRuntime
from config import Settings
from memory.memory_writer import load_datasets


ROOT = Path(__file__).resolve().parents[1]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(dir=ROOT, prefix=".api-live-test-")
        root = Path(self._temp.name)
        self.settings = Settings(data_dir=ROOT / "data", memory_backend="sqlite",
                                 sqlite_path=root / "memory.sqlite3",
                                 workflow_db_path=root / "workflows.sqlite3",
                                 api_cors_origins=("http://localhost:5173",))
        self.runtime = ApiRuntime(self.settings)
        self.client = TestClient(create_app(self.settings, self.runtime))

    def tearDown(self):
        self.runtime.workflow_store.close()
        self._temp.cleanup()

    def upload_demo_history(self):
        return self.client.post("/api/memory/uploads", files={
            "file": ("remediation_history.json", (ROOT / "data" / "remediation_history.json").read_bytes(),
                     "application/json"),
        })

    def test_health_capabilities_and_openapi(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["health"], "/api/health")
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["memory_backend"], "sqlite")
        self.assertTrue(health.json()["simulated_actions"])
        self.assertEqual(self.client.get("/health").json(), health.json())
        capabilities = self.client.get("/api/capabilities").json()
        self.assertTrue(capabilities["persistent_memory"])
        self.assertTrue(capabilities["file_ingestion"])
        self.assertEqual(capabilities["embedding_provider"], "none")
        self.assertFalse(capabilities["authenticated_approvals"])
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/incidents/investigate", paths)
        cors = self.client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                                           "Access-Control-Request-Method": "GET"})
        self.assertEqual(cors.status_code, 200)
        self.assertEqual(cors.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_empty_dashboard_stays_available_when_hindsight_is_offline(self):
        settings = Settings(data_dir=ROOT / "data", memory_backend="hindsight",
                            hindsight_base_url="http://127.0.0.1:1", hindsight_timeout=0.1,
                            workflow_db_path=Path(self._temp.name) / "offline-workflows.sqlite3")
        runtime = ApiRuntime(settings)
        try:
            client = TestClient(create_app(settings, runtime))
            overview = client.get("/api/ui/overview")
            self.assertEqual(overview.status_code, 200)
            self.assertEqual(overview.json()["learningScore"], 0)
            evaluation = client.get("/api/ui/evaluation")
            self.assertEqual(evaluation.status_code, 200)
            self.assertEqual(evaluation.json()["progress"][0]["label"], "Empty memory")
        finally:
            runtime.workflow_store.close()

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
        self.assertEqual(self.upload_demo_history().status_code, 201)
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
        try:
            client = TestClient(create_app(self.settings, runtime))
            self.assertEqual(client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"}).status_code, 200)
            response = client.post("/api/demo/workflows", json={"scenario": "high-risk-approval"})
            self.assertEqual(response.status_code, 503)
        finally:
            runtime.workflow_store.close()

    def test_ui_contract_supports_live_frontend_workflow(self):
        incidents = self.client.get("/api/ui/incidents")
        self.assertEqual(incidents.status_code, 200)
        self.assertEqual(incidents.json(), [])
        self.assertEqual(self.client.get("/api/ui/memory").json(), [])
        self.assertEqual(self.upload_demo_history().status_code, 201)
        incidents = self.client.get("/api/ui/incidents")
        self.assertEqual(len(incidents.json()), len(self.runtime.cases))
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
        self.assertEqual(self.upload_demo_history().status_code, 201)
        pending = self.client.post("/api/ui/incidents/TEST-003/workflow").json()
        self.assertEqual(pending["status"], "HUMAN_APPROVAL_REQUIRED")
        self.assertEqual(self.client.get("/api/ui/overview").json()["pendingApprovals"], 1)
        pending_rows = self.client.get("/api/ui/incidents").json()
        self.assertEqual([row["incident_id"] for row in pending_rows
                          if row["status"] == "APPROVAL_REQUIRED"], ["TEST-003"])
        approved = self.client.post("/api/ui/incidents/TEST-003/approval", json={
            "request_id": pending["decision"]["request_id"], "approved": True, "reviewer": "operator",
        })
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "SUCCESS")
        self.assertEqual(self.client.get("/api/ui/overview").json()["pendingApprovals"], 0)

    def test_ui_memory_and_evaluation_are_live(self):
        before = self.client.get("/api/ui/evaluation").json()
        self.assertEqual(before["metrics"][0]["withMemory"], "0.0%")
        self.assertEqual(self.upload_demo_history().status_code, 201)
        memory = self.client.get("/api/ui/memory", params={"service": "queue-service", "result": "FAILED"})
        self.assertEqual(memory.status_code, 200)
        self.assertEqual(len(memory.json()), 3)
        evaluation = self.client.get("/api/ui/evaluation")
        self.assertEqual(evaluation.status_code, 200)
        self.assertGreater(float(evaluation.json()["metrics"][0]["withMemory"].rstrip("%")), 0)
        self.assertEqual(evaluation.json()["backend"], "sqlite")
        self.assertEqual(evaluation.json()["progress"][0]["label"], "Empty memory")
        self.assertEqual(evaluation.json()["progress"][-1]["label"], "Uploaded remediation_history.json")
        self.assertEqual(self.client.post("/api/ui/incidents/TEST-001/workflow").status_code, 200)
        after_workflow = self.client.get("/api/ui/evaluation").json()
        self.assertEqual(after_workflow["progress"][-1]["label"], "Verified TEST-001")
        self.assertEqual(len(after_workflow["cases"]), len(self.runtime.cases))
        self.assertEqual(self.client.post("/api/ui/reset").json()["status"], "RESET")
        self.assertEqual(self.client.get("/api/ui/incidents").json(), [])

    def test_ui_uploads_persist_and_can_be_deleted(self):
        uploaded = self.upload_demo_history()
        upload_id = uploaded.json()["upload_id"]
        jobs = self.client.get("/api/ui/uploads").json()
        self.assertEqual([job["id"] for job in jobs], [upload_id])
        self.assertEqual(jobs[0]["storedIncidents"], 18)
        self.assertEqual(self.client.delete(f"/api/ui/uploads/{upload_id}").status_code, 204)
        self.assertEqual(self.client.get("/api/ui/uploads").json(), [])
        self.assertEqual(self.client.get("/api/ui/incidents").json(), [])

    def test_ui_upload_is_queued_and_completes(self):
        response = self.client.post("/api/ui/uploads", files={
            "file": ("remediation_history.json", (ROOT / "data" / "remediation_history.json").read_bytes(),
                     "application/json"),
        })
        self.assertEqual(response.status_code, 202)
        upload_id = response.json()["id"]
        self.assertIn(response.json()["stage"], {"uploading", "embedding"})
        job = response.json()
        for _ in range(100):
            jobs = self.client.get("/api/ui/uploads").json()
            job = next(item for item in jobs if item["id"] == upload_id)
            if job["stage"] in {"completed", "failed"}:
                break
            time.sleep(0.02)
        self.assertEqual(job["stage"], "completed")
        self.assertEqual(job["storedIncidents"], 18)
        self.assertEqual(len(self.client.get("/api/ui/incidents").json()), len(self.runtime.cases))
        # The real evaluation deliberately continues after storage completes.
        # Wait for its checkpoint before removing this test's SQLite directory.
        for _ in range(100):
            progress = self.client.get("/api/ui/evaluation").json()["progress"]
            if progress[-1]["label"] == "Uploaded remediation_history.json":
                break
            time.sleep(0.02)
        self.assertEqual(progress[-1]["label"], "Uploaded remediation_history.json")

    def test_all_cases_learn_resolve_and_retain_in_any_order(self):
        for seed in (7, 29):
            self.runtime.reset_ui_session()
            cases = list(self.runtime.cases)
            random.Random(seed).shuffle(cases)
            for case in cases:
                key = case.incident.incident_id
                with self.subTest(seed=seed, incident=key):
                    response = self.client.post(f"/api/ui/incidents/{key}/workflow")
                    self.assertEqual(response.status_code, 200, response.text)
                    result = response.json()
                    if case.incident.severity in {"HIGH", "CRITICAL"}:
                        self.assertEqual(result["status"], "HUMAN_APPROVAL_REQUIRED")
                    if result["status"] == "HUMAN_APPROVAL_REQUIRED":
                        self.assertTrue(result["memory_stored"])
                        self.assertIsNotNone(self.runtime.ui_memory.get_incident_memory(result["observation_id"]))
                        result = self.client.post(f"/api/ui/incidents/{key}/approval", json={
                            "request_id": result["decision"]["request_id"], "approved": True, "reviewer": "test",
                        }).json()
                    self.assertEqual(result["status"], "SUCCESS")
                    self.assertTrue(result["memory_stored"])
                    record = self.runtime.ui_memory.get_incident_memory(key)
                    self.assertEqual(record.final_outcome, "SUCCESS")
                    self.assertEqual(self.client.post(f"/api/ui/incidents/{key}/workflow").json(), result)
            self.assertEqual(self.runtime.ui_completed, len(cases))
            evaluation = self.client.get("/api/ui/evaluation").json()
            self.assertEqual(evaluation["progress"][0]["score"], 0)
            self.assertGreater(evaluation["progress"][-1]["score"], 0)
            for row in evaluation["cases"]:
                self.assertNotIn(row["incidentId"], row["retrievedIds"])

    def test_unresolved_observation_can_retry_after_new_evidence(self):
        with patch.object(self.runtime, "history", []):
            result = self.client.post("/api/ui/incidents/TEST-003/workflow").json()
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(result["memory_stored"])
        observation = self.runtime.ui_memory.get_incident_memory(result["observation_id"])
        self.assertEqual(observation.record_kind, "observation")
        self.assertIsNone(observation.final_outcome)
        self.assertEqual(self.upload_demo_history().status_code, 201)
        retried = self.client.post("/api/ui/incidents/TEST-003/workflow").json()
        self.assertEqual(retried["status"], "HUMAN_APPROVAL_REQUIRED")

    def test_dashboard_bank_pending_reviews_and_learning_survive_restart(self):
        self.upload_demo_history()
        waiting = self.client.post("/api/ui/incidents/HELD-007/workflow").json()
        self.assertEqual(waiting["status"], "HUMAN_APPROVAL_REQUIRED")
        reopened = ApiRuntime(self.settings)
        try:
            self.assertEqual(reopened._ui_session, self.runtime._ui_session)
            self.assertEqual(len(reopened.memory_records()), len(self.runtime.memory_records()))
            client = TestClient(create_app(self.settings, reopened))
            result = client.post("/api/ui/incidents/HELD-007/approval", json={
                "request_id": waiting["decision"]["request_id"], "approved": True, "reviewer": "test",
            }).json()
            self.assertEqual(result["status"], "SUCCESS")
            self.assertTrue(result["memory_stored"])
        finally:
            reopened.workflow_store.close()

    def test_failed_retain_can_retry_without_executing_twice(self):
        self.upload_demo_history()
        store = self.runtime.ui_memory.store_incident_memory
        def fail_outcome(record):
            if record.incident.incident_id == "TEST-001":
                raise RuntimeError("memory temporarily offline")
            return store(record)
        with patch.object(self.runtime.ui_memory, "store_incident_memory", side_effect=fail_outcome):
            self.assertEqual(self.client.post("/api/ui/incidents/TEST-001/workflow").status_code, 503)
        run = self.runtime._ui_runs["TEST-001"]
        with patch.object(run.workflow.world, "remediate", side_effect=AssertionError("Repeated execution")):
            result = self.client.post("/api/ui/incidents/TEST-001/workflow").json()
        self.assertEqual(result["status"], "SUCCESS")
        self.assertTrue(result["memory_stored"])

    def test_evaluation_error_does_not_hide_retained_outcome(self):
        self.upload_demo_history()
        with patch.object(self.runtime, "_measure_memory", side_effect=RuntimeError("recall unavailable")):
            response = self.client.post("/api/ui/incidents/TEST-001/workflow")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["memory_stored"])
        report = self.client.get("/api/ui/evaluation").json()
        self.assertEqual(report["evaluationStatus"], "error")
        self.assertEqual(report["evaluationError"], "recall unavailable")

    def test_evaluation_uses_recalled_memory_without_model_generation(self):
        self.upload_demo_history()
        with patch.object(self.runtime, "llm") as llm:
            report = self.runtime._measure_memory()
        llm.generate.assert_not_called()
        self.assertGreater(report["score"], 0)
        self.assertEqual(len(report["rows"]), 12)
        self.assertEqual(self.client.post("/api/ui/evaluation/refresh").status_code, 202)

    def test_interrupted_evaluation_is_marked_pending_on_restart(self):
        self.upload_demo_history()
        self.runtime._evaluation_pending = True
        self.runtime._persist_dashboard()
        reopened = ApiRuntime(self.settings)
        try:
            self.assertTrue(reopened._evaluation_pending)
            with patch.object(reopened, "_capture_evaluation") as capture:
                reopened.evaluation_report()
            capture.assert_called_once_with("Resumed memory evaluation")
        finally:
            reopened.workflow_store.close()


if __name__ == "__main__":
    unittest.main()
