"""Opt-in integration check for Postgres persistence across API restarts."""

import os
from pathlib import Path
import unittest
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg

from api.app import create_app
from api.runtime import ApiRuntime
from config import Settings


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to a disposable local Postgres database")
class PostgresApiTests(unittest.TestCase):
    def test_state_survives_runtime_restart(self):
        base_url = os.environ["TEST_DATABASE_URL"]
        if urlsplit(base_url).hostname not in {"localhost", "127.0.0.1"}:
            self.fail("TEST_DATABASE_URL must point to a disposable local database")
        schema = "api_test_" + uuid4().hex
        with psycopg.connect(base_url) as connection:
            connection.execute(f"CREATE SCHEMA {schema}")
        suffix = "&" if "?" in base_url else "?"
        test_url = base_url + suffix + urlencode({"options": f"-csearch_path={schema}"})
        settings = Settings(data_dir=ROOT / "data", memory_backend="postgres",
                            database_url=test_url, hindsight_bank_id=schema)
        try:
            runtime = ApiRuntime(settings)
            client = TestClient(create_app(settings, runtime))
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["memory_ready"])
            with (ROOT / "data/remediation_history.json").open("rb") as source:
                uploaded = client.post("/api/memory/uploads", files={
                    "file": ("remediation_history.json", source, "application/json")})
            self.assertEqual(uploaded.status_code, 201)
            completed = client.post("/api/ui/incidents/TEST-001/workflow")
            self.assertEqual(completed.json()["status"], "SUCCESS")
            pending = client.post("/api/ui/incidents/TEST-003/workflow").json()
            approved = client.post("/api/ui/incidents/TEST-003/approval", json={
                "request_id": pending["decision"]["request_id"],
                "approved": True, "reviewer": "integration-test"})
            self.assertEqual(approved.json()["status"], "SUCCESS")
            runtime.workflow_store.close()

            restarted = ApiRuntime(settings)
            client = TestClient(create_app(settings, restarted))
            self.assertEqual(client.get("/api/ui/overview").json()["resolved"], 2)
            self.assertEqual(client.get("/api/ui/uploads").json()[0]["stage"], "completed")
            self.assertTrue(client.get("/api/ui/memory").json())
            restarted.workflow_store.close()
        finally:
            with psycopg.connect(base_url) as connection:
                connection.execute(f"DROP SCHEMA {schema} CASCADE")
