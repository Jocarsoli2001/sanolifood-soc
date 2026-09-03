from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "evalctl.py"
SPEC = importlib.util.spec_from_file_location("evalctl", MODULE_PATH)
assert SPEC and SPEC.loader
evalctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evalctl)


class EvaluationControlTests(unittest.TestCase):
    def test_catalog_has_eight_unique_bounded_scenarios(self) -> None:
        payload = evalctl.catalog()
        scenarios = payload["scenarios"]
        self.assertEqual([item["id"] for item in scenarios], [f"SCN-{n:03d}" for n in range(1, 9)])
        self.assertEqual(len({item["expected_rule_id"] for item in scenarios}), 8)
        self.assertTrue(all(item["request_budget"] <= 30 for item in scenarios))

    def test_run_identifier_is_attributable_and_safe(self) -> None:
        run_id = evalctl.make_run_id("SCN-001")
        self.assertRegex(run_id, evalctl.RUN_ID_RE)
        self.assertTrue(run_id.startswith("SF-EVAL-SCN-001-"))

    def test_run_directory_rejects_path_input(self) -> None:
        with self.assertRaises(evalctl.EvaluationError):
            evalctl.run_dir("../../outside")

    def test_ssh_destinations_are_fixed(self) -> None:
        self.assertRegex("analyst@10.20.0.30", evalctl.KALI_SSH_RE)
        self.assertNotRegex("analyst@10.20.0.31", evalctl.KALI_SSH_RE)
        self.assertRegex("jose@10.20.0.20", evalctl.WINDOWS_SSH_RE)

    def test_metric_intervals_are_independent(self) -> None:
        result = {
            "stimulus_started_at": "2026-08-31T12:00:00+00:00",
            "wazuh_detected_at": "2026-08-31T12:00:02+00:00",
        }
        incident = {
            "received_at": "2026-08-31T12:00:03+00:00",
            "triaged_at": "2026-08-31T12:00:04+00:00",
            "decided_at": "2026-08-31T12:00:10+00:00",
            "response_started_at": "2026-08-31T12:00:11+00:00",
            "contained_at": "2026-08-31T12:00:12+00:00",
            "rolled_back_at": "2026-08-31T12:00:13+00:00",
        }
        values = evalctl.metrics(result, incident)
        self.assertEqual(values["stimulus_to_wazuh_seconds"], 2.0)
        self.assertEqual(values["wazuh_to_soar_seconds"], 1.0)
        self.assertEqual(values["soar_triage_seconds"], 1.0)
        self.assertEqual(values["analyst_decision_seconds"], 6.0)
        self.assertEqual(values["containment_to_rollback_seconds"], 1.0)

    def test_percentile_uses_nearest_rank(self) -> None:
        self.assertEqual(evalctl.percentile([1.0, 2.0, 3.0, 4.0], 0.95), 4.0)
        self.assertIsNone(evalctl.percentile([], 0.95))

    def test_summary_counts_only_final_pass_as_coverage(self) -> None:
        original_results = evalctl.RESULTS_DIR
        original_runs = evalctl.RUNS_DIR
        with tempfile.TemporaryDirectory() as temporary:
            evalctl.RESULTS_DIR = Path(temporary)
            evalctl.RUNS_DIR = Path(temporary) / "runs"
            passed = evalctl.RUNS_DIR / "pass"
            pending = evalctl.RUNS_DIR / "pending"
            passed.mkdir(parents=True)
            pending.mkdir(parents=True)
            evalctl.write_json(
                passed / "result.json",
                {
                    "run_id": "pass",
                    "scenario_id": "SCN-001",
                    "status": "PASS",
                    "response_mode": "dry-run",
                    "actions": [],
                    "metrics": {},
                },
            )
            evalctl.write_json(
                pending / "result.json",
                {
                    "run_id": "pending",
                    "scenario_id": "SCN-002",
                    "status": "PASS_PENDING_DECISION",
                    "response_mode": "dry-run",
                    "actions": [],
                    "metrics": {},
                },
            )
            summary = evalctl.build_summary()
            self.assertEqual(summary["complete_scenarios"], ["SCN-001"])
            self.assertEqual(summary["pending_decision_count"], 1)
            self.assertEqual(summary["scenario_coverage_percent"], 12.5)
        evalctl.RESULTS_DIR = original_results
        evalctl.RUNS_DIR = original_runs


if __name__ == "__main__":
    unittest.main()
