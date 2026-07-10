from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check_reviewer_study.py"


class ReviewerStudyContractTests(unittest.TestCase):
    def test_study_contract_self_check_passes_without_claiming_results(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(CHECKER)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertIn("synthetic self-test only", result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith("PASS reviewer_study_v0"))


if __name__ == "__main__":
    unittest.main()
