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

    def test_negative_metric_interval_is_invalid(self) -> None:
        self.assertIsNone(
            evalctl.seconds_between(
                "2026-09-01T13:30:12.147+00:00",
                "2026-09-01T13:30:12.738+00:00",
            )
        )
        with self.assertRaises(evalctl.EvaluationError):
            evalctl.validate_core_timing(
                {
                    "stimulus_to_wazuh_seconds": None,
                    "wazuh_to_soar_seconds": 0.7,
                    "soar_triage_seconds": 0.1,
                    "end_to_end_triage_seconds": 0.8,
                }
            )

    def test_clock_skew_uses_millisecond_precision(self) -> None:
        self.assertEqual(evalctl.clock_skew_seconds(1_000_250, 1_000.0), 0.25)

    def test_live_control_plan_keeps_only_reversible_response_actions(self) -> None:
        plan = evalctl.live_control_plan(
            {
                "actions": [
                    {
                        "id": "evidence",
                        "action_type": "collect_evidence",
                        "automatic": True,
                        "reversible": False,
                        "status": "completed",
                    },
                    {
                        "id": "control",
                        "action_type": "quality_guard",
                        "automatic": False,
                        "reversible": True,
                        "status": "pending_approval",
                        "target": "quality-release",
                    },
                ]
            }
        )
        self.assertEqual(
            plan,
            [
                {
                    "id": "control",
                    "action_type": "quality_guard",
                    "target": "quality-release",
                }
            ],
        )

    def test_live_application_guard_must_change_with_the_phase(self) -> None:
        class FakeClient:
            def __init__(self, enforced: bool):
                self.enforced = enforced

            def enforcement_probe(self, control_type: str, target: str) -> dict:
                return {
                    "control_type": control_type,
                    "target": target,
                    "decision": "deny" if self.enforced else "allow",
                    "enforced": self.enforced,
                    "action_id": "control" if self.enforced else None,
                }

        plan = [
            {
                "id": "control",
                "action_type": "quality_guard",
                "target": "quality-release",
            }
        ]
        before = evalctl.verify_live_control_phase(
            FakeClient(False),
            plan,
            phase="before",
            expected_enforced=False,
            kali_ssh="",
            run_id="SF-EVAL-SCN-006-20260902T120000Z-1234abcd",
        )
        active = evalctl.verify_live_control_phase(
            FakeClient(True),
            plan,
            phase="active",
            expected_enforced=True,
            kali_ssh="",
            run_id="SF-EVAL-SCN-006-20260902T120000Z-1234abcd",
        )
        self.assertEqual(before["expected_decision"], "allow")
        self.assertEqual(active["expected_decision"], "deny")

        with self.assertRaises(evalctl.EvaluationError):
            evalctl.verify_live_control_phase(
                FakeClient(False),
                plan,
                phase="active",
                expected_enforced=True,
                kali_ssh="",
                run_id="SF-EVAL-SCN-006-20260902T120000Z-1234abcd",
            )

    def test_percentile_uses_nearest_rank(self) -> None:
        self.assertEqual(evalctl.percentile([1.0, 2.0, 3.0, 4.0], 0.95), 4.0)
        self.assertIsNone(evalctl.percentile([], 0.95))

    def test_precise_receipt_excludes_ssh_authentication_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            result = {
                "dispatch_started_at": "2026-09-01T01:38:57+00:00",
                "stimulus_completed_at": "2026-09-01T01:39:06+00:00",
            }
            precise = evalctl.apply_precise_stimulus_time(
                destination,
                result,
                {"started_at": "2026-09-01T01:39:05+00:00"},
            )
            self.assertEqual(precise.isoformat(), "2026-09-01T01:39:05+00:00")
            self.assertEqual(result["stimulus_timing_source"], "stimulus_receipt")

    def test_summary_counts_only_final_pass_as_coverage(self) -> None:
        original_results = evalctl.RESULTS_DIR
        original_runs = evalctl.RUNS_DIR
        with tempfile.TemporaryDirectory() as temporary:
            evalctl.RESULTS_DIR = Path(temporary)
            evalctl.RUNS_DIR = Path(temporary) / "runs"
            passed = evalctl.RUNS_DIR / "pass"
            pending = evalctl.RUNS_DIR / "pending"
            invalid = evalctl.RUNS_DIR / "invalid"
            passed.mkdir(parents=True)
            pending.mkdir(parents=True)
            invalid.mkdir(parents=True)
            evalctl.write_json(
                passed / "result.json",
                {
                    "run_id": "pass",
                    "scenario_id": "SCN-001",
                    "status": "PASS",
                    "response_mode": "dry-run",
                    "timing_integrity": "valid",
                    "actions": [],
                    "metrics": {"stimulus_to_wazuh_seconds": 2.0},
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
                    "metrics": {"stimulus_to_wazuh_seconds": 0.1},
                },
            )
            evalctl.write_json(
                invalid / "result.json",
                {
                    "run_id": "invalid",
                    "scenario_id": "SCN-003",
                    "status": "PASS",
                    "response_mode": "dry-run",
                    "actions": [],
                    "metrics": {"stimulus_to_wazuh_seconds": 0.0},
                },
            )
            summary = evalctl.build_summary()
            self.assertEqual(summary["complete_scenarios"], ["SCN-001"])
            self.assertEqual(summary["pending_decision_count"], 1)
            self.assertEqual(summary["scenario_coverage_percent"], 12.5)
            self.assertEqual(summary["invalid_timing_count"], 1)
            self.assertEqual(summary["metrics"]["stimulus_to_wazuh_seconds"]["samples"], 1)
            self.assertEqual(summary["metrics"]["stimulus_to_wazuh_seconds"]["mean"], 2.0)
        evalctl.RESULTS_DIR = original_results
        evalctl.RUNS_DIR = original_runs

    def test_summary_requires_live_effect_verification(self) -> None:
        original_results = evalctl.RESULTS_DIR
        original_runs = evalctl.RUNS_DIR
        with tempfile.TemporaryDirectory() as temporary:
            evalctl.RESULTS_DIR = Path(temporary)
            evalctl.RUNS_DIR = Path(temporary) / "runs"
            verified = evalctl.RUNS_DIR / "verified"
            unverified = evalctl.RUNS_DIR / "unverified"
            verified.mkdir(parents=True)
            unverified.mkdir(parents=True)
            common = {
                "scenario_id": "SCN-002",
                "status": "PASS",
                "response_mode": "live",
                "timing_integrity": "valid",
                "actions": [
                    {"status": "rolled_back"},
                ],
                "metrics": {"stimulus_to_wazuh_seconds": 1.0},
            }
            evalctl.write_json(
                verified / "result.json",
                {
                    **common,
                    "run_id": "verified",
                    "live_control_verification": {"status": "PASS"},
                },
            )
            evalctl.write_json(
                unverified / "result.json",
                {
                    **common,
                    "run_id": "unverified",
                    "metrics": {"stimulus_to_wazuh_seconds": 99.0},
                },
            )
            summary = evalctl.build_summary()
            self.assertEqual(summary["live_verified_run_count"], 1)
            self.assertEqual(summary["live_rollback_count"], 2)
            self.assertEqual(
                summary["metrics"]["stimulus_to_wazuh_seconds"]["samples"], 1
            )
            self.assertEqual(
                summary["metrics"]["stimulus_to_wazuh_seconds"]["mean"], 1.0
            )
        evalctl.RESULTS_DIR = original_results
        evalctl.RUNS_DIR = original_runs


if __name__ == "__main__":
    unittest.main()
