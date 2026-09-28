"""Dataset checkpoint report tests."""

from pathlib import Path
import unittest

from evaluation.dataset_audit import audit


ROOT = Path(__file__).resolve().parents[1]


class DatasetAuditTests(unittest.TestCase):
    def test_dataset_checkpoint_is_balanced_and_leak_free(self):
        report = audit(ROOT / "data")
        self.assertTrue(report["passed"])
        self.assertEqual(report["counts"], {"historical_incidents": 18,
                                             "held_out_cases": 12, "outcomes": 54})
        self.assertEqual(set(report["history_services"]), set(report["held_out_services"]))
        self.assertEqual(len(report["sha256"]), 3)
