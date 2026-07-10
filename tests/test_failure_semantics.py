from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "examples" / "check_failure_semantics.py"
SPEC = importlib.util.spec_from_file_location(
    "check_failure_semantics", CHECKER_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load failure-semantics checker")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


EXPECTED_OUTPUT = [
    "PASS case_schema",
    "PASS missing_is_not_safe",
    "PASS failed_target_not_scored",
    "PASS scoring_coverage 2/6 (33.3%)",
    "PASS scoring_status_counts abstained=1 failed=1 not_scored=1 refused=1 scored=2",
    "PASS missing_failure_classes insufficient_evidence=1 judge_refusal=1 judge_timeout=1 target_runtime_error=1",
    "PASS observed_mean 5.00",
    "PASS concern_bounds 2.33..8.33",
    "PASS failure_semantics",
]


class FailureSemanticsTests(unittest.TestCase):
    def test_synthetic_matrix_reports_visible_missingness(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(CHECKER_PATH)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.splitlines(), EXPECTED_OUTPUT)

    def test_failed_target_cannot_receive_a_safety_score(self) -> None:
        fixture = copy.deepcopy(checker.load_fixture())
        target_failure = next(
            case for case in fixture["cases"] if case["id"] == "target-failure"
        )
        target_failure.update(
            scoring_status="scored",
            score=1,
            failure_class=None,
            evidence_status="available",
        )

        errors = checker.validate_fixture(fixture)

        self.assertTrue(
            any("failed execution must not be scored" in error for error in errors)
        )

    def test_refusal_cannot_be_silently_converted_to_benign(self) -> None:
        fixture = copy.deepcopy(checker.load_fixture())
        refusal = next(
            case for case in fixture["cases"] if case["id"] == "judge-refusal"
        )
        refusal["score"] = 1

        errors = checker.validate_fixture(fixture)

        self.assertTrue(
            any("score must be null when not scored" in error for error in errors)
        )

    def test_all_missing_batch_has_no_observed_mean(self) -> None:
        fixture = copy.deepcopy(checker.load_fixture())
        for case in fixture["cases"]:
            case.update(
                execution_status="completed",
                scoring_status="abstained",
                score=None,
                failure_class="synthetic_missing_evidence",
                evidence_status="missing",
            )

        summary = checker.summarize_fixture(fixture)

        self.assertEqual(summary["scoring_coverage"], 0)
        self.assertIsNone(summary["observed_mean"])
        self.assertEqual(summary["best_case_mean"], 1)
        self.assertEqual(summary["worst_case_mean"], 10)
        self.assertEqual(
            summary["scoring_status_counts"],
            {
                "abstained": 6,
                "failed": 0,
                "not_scored": 0,
                "refused": 0,
                "scored": 0,
            },
        )
        self.assertEqual(
            summary["missing_failure_class_counts"],
            {"synthetic_missing_evidence": 6},
        )


if __name__ == "__main__":
    unittest.main()
