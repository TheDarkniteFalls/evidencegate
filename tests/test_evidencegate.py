from __future__ import annotations

import copy
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import evidencegate


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def run_git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class EvidenceGateReceiptTests(unittest.TestCase):
    def test_legacy_receipt_remains_supported_and_labelled(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = evidencegate.main([str(EXAMPLES / "good-run.json")])

        self.assertEqual(result, 0)
        self.assertIn("PASS EvidenceGate legacy receipt", output.getvalue())
        self.assertIn("not revision-bound", output.getvalue())

    def test_v1_fixture_validates_and_render_preserves_status(self) -> None:
        packet = evidencegate.load_packet(EXAMPLES / "v1-review-ready.json")

        self.assertEqual(evidencegate.validate_packet(packet), [])
        rendered = evidencegate.render_packet(packet)
        self.assertIn("# EvidenceGate v1 receipt", rendered)
        self.assertIn("[skipped; optional] Windows smoke test", rendered)
        self.assertIn("[unknown; optional] Commit-history review", rendered)
        self.assertIn("`claim:regression-fixed`", rendered)
        self.assertIn(evidencegate.BOUNDARY, rendered)

    def test_stale_evidence_and_unknown_claim_reference_fail(self) -> None:
        stale = evidencegate.validate_packet(
            evidencegate.load_packet(EXAMPLES / "v1-stale-evidence.json")
        )
        unsupported = evidencegate.validate_packet(
            evidencegate.load_packet(EXAMPLES / "v1-unsupported-claim.json")
        )

        self.assertIn(
            "checks[1].revision does not match subject.head_sha", stale
        )
        self.assertIn(
            "claims[1] references unknown evidence: check:behavior", unsupported
        )

    def test_failed_required_check_is_preserved_but_not_review_ready(self) -> None:
        packet = evidencegate.load_packet(EXAMPLES / "v1-not-review-ready.json")

        self.assertEqual(evidencegate.validate_packet(packet), [])
        self.assertIn(
            "required check is not passing: check:behavior (failed)",
            evidencegate.review_readiness_errors(packet),
        )
        self.assertIn(
            "[failed; required] Behavioral regression check",
            evidencegate.render_packet(packet),
        )

    def test_human_and_public_safety_reviews_must_target_head(self) -> None:
        packet = evidencegate.load_packet(EXAMPLES / "v1-review-ready.json")
        packet["human_review"]["reviewed_head_sha"] = "3" * 40
        packet["public_safety"]["reviewed_head_sha"] = "4" * 40

        errors = evidencegate.validate_packet(packet)

        self.assertIn(
            "human_review.reviewed_head_sha does not match subject.head_sha", errors
        )
        self.assertIn(
            "public_safety.reviewed_head_sha does not match subject.head_sha", errors
        )


class EvidenceGateRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary_directory.name)
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.name", "Synthetic Maintainer")
        run_git(self.repo, "config", "user.email", "synthetic-maintainer.invalid")
        (self.repo / "README.md").write_text("synthetic base\n", encoding="utf-8")
        run_git(self.repo, "add", "README.md")
        run_git(self.repo, "commit", "-q", "-m", "synthetic base")
        self.base_sha = run_git(self.repo, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def commit_changes(self, changes: dict[str, str]) -> str:
        for relative_path, content in changes.items():
            path = self.repo / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        run_git(self.repo, "add", "--", *changes)
        run_git(self.repo, "commit", "-q", "-m", "synthetic change")
        return run_git(self.repo, "rev-parse", "HEAD")

    def packet_for(self, head_sha: str, files: list[str]) -> dict:
        packet = copy.deepcopy(
            evidencegate.load_packet(EXAMPLES / "v1-review-ready.json")
        )
        packet["summary"] = "Changed synthetic files for repository verification."
        packet["subject"]["base_sha"] = self.base_sha
        packet["subject"]["head_sha"] = head_sha
        packet["files_touched"] = files
        packet["scope"]["allowed_paths"] = files
        packet["scope"]["protected_prefixes"] = [".env", ".git", "private"]
        for check in packet["checks"]:
            check["revision"] = head_sha
        packet["human_review"]["reviewed_head_sha"] = head_sha
        packet["public_safety"]["reviewed_head_sha"] = head_sha
        return packet

    def test_verify_matches_current_head_diff_and_scope(self) -> None:
        head_sha = self.commit_changes({"app.py": "print('synthetic')\n"})
        packet = self.packet_for(head_sha, ["app.py"])

        self.assertEqual(evidencegate.verify_repository(packet, self.repo), [])

    def test_verify_cli_reports_a_repository_pass(self) -> None:
        head_sha = self.commit_changes({"app.py": "print('synthetic')\n"})
        packet = self.packet_for(head_sha, ["app.py"])
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as receipt_directory:
            receipt_path = Path(receipt_directory) / "receipt.json"
            receipt_path.write_text(json.dumps(packet), encoding="utf-8")
            with redirect_stdout(output):
                result = evidencegate.main(
                    ["verify", str(receipt_path), "--repo", str(self.repo)]
                )

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "PASS EvidenceGate v1 repository verification",
        )

    def test_verify_detects_current_head_drift(self) -> None:
        head_sha = self.commit_changes({"app.py": "print('synthetic')\n"})
        packet = self.packet_for(head_sha, ["app.py"])
        self.commit_changes({"later.txt": "later edit\n"})

        errors = evidencegate.verify_repository(packet, self.repo)

        self.assertTrue(
            any(error.startswith("repository HEAD does not match") for error in errors)
        )

    def test_verify_requires_a_clean_work_tree(self) -> None:
        head_sha = self.commit_changes({"app.py": "print('synthetic')\n"})
        packet = self.packet_for(head_sha, ["app.py"])
        (self.repo / "app.py").write_text("print('dirty')\n", encoding="utf-8")

        errors = evidencegate.verify_repository(packet, self.repo)

        self.assertIn(
            "repository work tree has uncommitted or untracked changes; "
            "verify a clean checkout of subject.head_sha",
            errors,
        )

    def test_verify_detects_omitted_unauthorized_and_protected_path(self) -> None:
        head_sha = self.commit_changes(
            {
                "app.py": "print('synthetic')\n",
                "private/notes.txt": "synthetic protected text\n",
            }
        )
        packet = self.packet_for(head_sha, ["app.py"])

        errors = evidencegate.verify_repository(packet, self.repo)

        self.assertIn(
            "changed paths missing from files_touched: private/notes.txt", errors
        )
        self.assertIn(
            "Git diff includes paths outside scope.allowed_paths: private/notes.txt",
            errors,
        )
        self.assertIn("Git diff includes protected paths: private/notes.txt", errors)

    def test_verify_refuses_legacy_receipt(self) -> None:
        legacy = evidencegate.load_packet(EXAMPLES / "good-run.json")

        self.assertEqual(
            evidencegate.verify_repository(legacy, self.repo),
            [
                "legacy receipts cannot be repository-verified; migrate to schema_version 1"
            ],
        )


if __name__ == "__main__":
    unittest.main()
