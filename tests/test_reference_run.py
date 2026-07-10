from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_RUN = ROOT / "examples" / "run-v1-reference.py"
EXPECTED_OUTPUT = [
    "PASS focused_check",
    "PASS receipt_structure",
    "PASS repository_verification",
    "PASS stale_head_rejected",
    "PASS omitted_path_rejected",
    "PASS protected_path_rejected",
    "PASS v1_reference_run",
]


class ReferenceRunTests(unittest.TestCase):
    def test_reference_run_exercises_the_detached_v1_lifecycle(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(REFERENCE_RUN)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.splitlines(), EXPECTED_OUTPUT)


if __name__ == "__main__":
    unittest.main()
