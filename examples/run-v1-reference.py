#!/usr/bin/env python3
"""Run a temporary, detached EvidenceGate v1 reference flow."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import evidencegate  # noqa: E402


FOCUSED_COMMAND = "python -B -m unittest discover -s tests -v"
EXPECTED_OUTPUT = [
    "PASS focused_check",
    "PASS receipt_structure",
    "PASS repository_verification",
    "PASS stale_head_rejected",
    "PASS omitted_path_rejected",
    "PASS protected_path_rejected",
    "PASS v1_reference_run",
]


class ReferenceRunError(RuntimeError):
    """Raised when the synthetic reference flow violates an expectation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReferenceRunError(message)


def run_command(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def run_git(repo: Path, *arguments: str) -> str:
    result = run_command(["git", *arguments], repo)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise ReferenceRunError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout.strip()


def run_focused_check(repo: Path) -> None:
    result = run_command(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
        repo,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ReferenceRunError(f"focused check failed: {detail}")


def write_synthetic_base(repo: Path) -> None:
    (repo / "docs_export.py").write_text(
        """from pathlib import Path\n\n\ndef export_path(output_dir: Path, relative: str) -> Path:\n    return Path(relative)\n""",
        encoding="utf-8",
    )


def write_synthetic_fix(repo: Path) -> None:
    (repo / "docs_export.py").write_text(
        """from pathlib import Path\n\n\ndef export_path(output_dir: Path, relative: str) -> Path:\n    return output_dir / relative\n""",
        encoding="utf-8",
    )
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_export_paths.py").write_text(
        """import unittest\nfrom pathlib import Path\n\nfrom docs_export import export_path\n\n\nclass ExportPathTests(unittest.TestCase):\n    def test_relative_path_stays_under_output_directory(self) -> None:\n        output = Path(\"synthetic-export\")\n        self.assertEqual(\n            export_path(output, \"guide.md\"),\n            output / \"guide.md\",\n        )\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n""",
        encoding="utf-8",
    )


def build_receipt(base_sha: str, head_sha: str) -> dict:
    simulated = (
        "Simulated for this temporary public demonstration; no real identity, "
        "approval, or publication authority is asserted."
    )
    return {
        "schema_version": 1,
        "summary": (
            "Fixed a synthetic export-path regression and added a focused "
            "regression test."
        ),
        "subject": {
            "type": "git_change",
            "base_sha": base_sha,
            "head_sha": head_sha,
        },
        "scope": {
            "allowed_paths": ["docs_export.py", "tests/test_export_paths.py"],
            "protected_prefixes": [".env", ".git", "private"],
        },
        "files_touched": ["docs_export.py", "tests/test_export_paths.py"],
        "checks": [
            {
                "id": "check:regression",
                "name": "Synthetic export-path regression test",
                "command": FOCUSED_COMMAND,
                "status": "passed",
                "summary": "The focused regression test passed at the recorded head.",
                "scope": "Relative export paths remain under the output directory",
                "revision": head_sha,
                "required": True,
            }
        ],
        "claims": [
            {
                "id": "claim:regression-fixed",
                "text": "The synthetic export-path regression is fixed.",
                "evidence_refs": ["check:regression"],
            }
        ],
        "risks": [simulated],
        "human_review": {
            "status": "approved",
            "reviewer": "simulated-demo-reviewer",
            "reviewed_head_sha": head_sha,
            "summary": simulated,
        },
        "public_safety": {
            "status": "reviewed",
            "reviewed_head_sha": head_sha,
            "summary": simulated,
        },
    }


def run_reference() -> list[str]:
    output: list[str] = []
    with tempfile.TemporaryDirectory(prefix="evidencegate-v1-reference-") as temp:
        temp_root = Path(temp)
        repo = temp_root / "synthetic-repo"
        repo.mkdir()

        run_git(repo, "init", "-q")
        run_git(repo, "config", "user.name", "Synthetic Maintainer")
        run_git(repo, "config", "user.email", "synthetic-maintainer.invalid")

        write_synthetic_base(repo)
        run_git(repo, "add", "docs_export.py")
        run_git(repo, "commit", "-q", "-m", "Add synthetic export example")
        base_sha = run_git(repo, "rev-parse", "HEAD")

        write_synthetic_fix(repo)
        run_git(repo, "add", "docs_export.py", "tests/test_export_paths.py")
        run_git(repo, "commit", "-q", "-m", "Fix synthetic export path")
        head_sha = run_git(repo, "rev-parse", "HEAD")

        run_focused_check(repo)
        output.append("PASS focused_check")

        receipt_path = temp_root / "detached-receipt.json"
        receipt_path.write_text(
            json.dumps(build_receipt(base_sha, head_sha), indent=2) + "\n",
            encoding="utf-8",
        )
        receipt = evidencegate.load_packet(receipt_path)

        validation_errors = evidencegate.validate_packet(receipt)
        require(not validation_errors, "; ".join(validation_errors))
        rendered = evidencegate.render_packet(receipt)
        require("simulated-demo-reviewer" in rendered, "render omitted simulated review")
        require(evidencegate.BOUNDARY in rendered, "render omitted proof boundary")
        output.append("PASS receipt_structure")

        verification_errors = evidencegate.verify_repository(receipt, repo)
        require(not verification_errors, "; ".join(verification_errors))
        output.append("PASS repository_verification")

        stale = copy.deepcopy(receipt)
        stale["checks"][0]["revision"] = base_sha
        stale_errors = evidencegate.validate_packet(stale)
        require(
            any("revision does not match subject.head_sha" in error for error in stale_errors),
            "stale check revision was not rejected",
        )
        output.append("PASS stale_head_rejected")

        omitted = copy.deepcopy(receipt)
        omitted["files_touched"] = ["docs_export.py"]
        omitted_errors = evidencegate.verify_repository(omitted, repo)
        require(
            "changed paths missing from files_touched: tests/test_export_paths.py"
            in omitted_errors,
            "omitted changed path was not rejected",
        )
        output.append("PASS omitted_path_rejected")

        private = repo / "private"
        private.mkdir()
        (private / "notes.txt").write_text(
            "synthetic protected content\n", encoding="utf-8"
        )
        run_git(repo, "add", "private/notes.txt")
        run_git(repo, "commit", "-q", "-m", "Add protected-path negative case")
        protected_head = run_git(repo, "rev-parse", "HEAD")
        run_focused_check(repo)

        protected = copy.deepcopy(receipt)
        protected["subject"]["head_sha"] = protected_head
        protected["files_touched"].append("private/notes.txt")
        protected["scope"]["allowed_paths"].append("private/notes.txt")
        protected["checks"][0]["revision"] = protected_head
        protected["human_review"]["reviewed_head_sha"] = protected_head
        protected["public_safety"]["reviewed_head_sha"] = protected_head
        protected_errors = evidencegate.verify_repository(protected, repo)
        require(
            "files_touched include protected paths: private/notes.txt"
            in protected_errors,
            "protected changed path was not rejected",
        )
        output.append("PASS protected_path_rejected")

    output.append("PASS v1_reference_run")
    return output


def main() -> int:
    try:
        output = run_reference()
        require(output == EXPECTED_OUTPUT, "reference output changed unexpectedly")
    except (OSError, ReferenceRunError) as exc:
        print(f"FAIL v1_reference_run: {exc}")
        return 1
    for line in output:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
