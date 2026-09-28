"""Static deployment checks that run without Docker Desktop."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def test_container_runs_as_non_root_and_has_healthcheck(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("USER app", dockerfile)
        self.assertIn("healthcheck:", compose)
        self.assertIn("adaptive-runtime:/app/.runtime", compose)
        self.assertIn("APPROVAL_IDENTITIES_JSON", compose)
