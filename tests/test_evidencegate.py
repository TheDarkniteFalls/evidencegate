from __future__ import annotations

import copy
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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

    def test_validate_json_result_is_stable_and_does_not_echo_input_path(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = evidencegate.main(
                [
                    "validate",
                    str(EXAMPLES / "v1-review-ready.json"),
                    "--format",
                    "json",
                ]
            )

        document = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(
            document["contract_version"], evidencegate.CLI_RESULT_CONTRACT
        )
        self.assertEqual(document["operation"], "validate")
        self.assertTrue(document["ok"])
        self.assertFalse(document["repository_checked"])
        self.assertEqual(document["findings"], [])
        self.assertNotIn(str(EXAMPLES), output.getvalue())

    def test_validate_json_result_uses_stable_finding_codes(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = evidencegate.main(
                [
                    "validate",
                    str(EXAMPLES / "v1-stale-evidence.json"),
                    "--format",
                    "json",
                ]
            )

        document = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertFalse(document["ok"])
        self.assertIn(
            "receipt_revision_invalid",
            {finding["code"] for finding in document["findings"]},
        )

    def test_load_error_json_result_remains_machine_readable(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text('{"schema_version": 1, "schema_version": 2}')
            with redirect_stdout(output):
                result = evidencegate.main(
                    ["validate", str(invalid), "--format", "json"]
                )

        document = json.loads(output.getvalue())
        self.assertEqual(result, 2)
        self.assertEqual(document["receipt_version"], None)
        self.assertEqual(document["findings"][0]["code"], "packet_load_error")

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

    def test_load_rejects_ambiguous_or_non_standard_json(self) -> None:
        cases = {
            'duplicate JSON object key: schema_version': (
                '{"schema_version": 1, "schema_version": 2}'
            ),
            'non-standard JSON constant is not allowed: NaN': (
                '{"schema_version": 1, "score": NaN}'
            ),
            'non-finite JSON number is not allowed': (
                '{"schema_version": 1, "score": 1e400}'
            ),
            'unpaired Unicode surrogate is not allowed': (
                r'{"schema_version": 1, "summary": "\ud800"}'
            ),
            'packet JSON nesting is too deep': "[" * 2000 + "0" + "]" * 2000,
        }
        with tempfile.TemporaryDirectory() as directory:
            for expected, text in cases.items():
                path = Path(directory) / f"case-{len(text)}.json"
                path.write_text(text, encoding="utf-8")
                with self.subTest(expected=expected):
                    with self.assertRaisesRegex(ValueError, expected):
                        evidencegate.load_packet(path)

    def test_load_enforces_the_packet_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversized.json"
            path.write_bytes(b" " * (evidencegate.MAX_PACKET_BYTES + 1))

            with self.assertRaisesRegex(ValueError, "maximum supported size"):
                evidencegate.load_packet(path)

    def test_v1_unknown_fields_are_rejected_but_extensions_are_explicit(self) -> None:
        packet = evidencegate.load_packet(EXAMPLES / "v1-review-ready.json")
        packet["policy_override"] = "approved"

        self.assertIn(
            "policy_override is not defined by EvidenceGate v1; "
            "put non-authoritative metadata under extensions",
            evidencegate.validate_packet(packet),
        )

        packet.pop("policy_override")
        packet["extensions"] = {
            "https://example.invalid/review-metadata/v1": {
                "ticket": "SYNTHETIC-1",
                "policy_override": "approved",
            }
        }
        self.assertEqual(evidencegate.validate_packet(packet), [])
        self.assertNotIn("SYNTHETIC-1", evidencegate.render_packet(packet))

        packet["checks"][0]["policy_override"] = "approved"
        self.assertTrue(
            any(
                error.startswith("checks[1].policy_override is not defined")
                for error in evidencegate.validate_packet(packet)
            )
        )

    def test_render_neutralizes_markdown_and_html_structure(self) -> None:
        packet = evidencegate.load_packet(EXAMPLES / "v1-review-ready.json")
        packet["summary"] = (
            "Ordinary summary.\n\n"
            "## Human review\n\n"
            "<script>alert('synthetic')</script>"
        )
        packet["human_review"]["reviewer"] = "maintainer\n## injected reviewer"
        packet["checks"][0]["command"] = "printf `synthetic`"

        rendered = evidencegate.render_packet(packet)

        self.assertEqual(rendered.count("## Human review"), 1)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("\n## injected reviewer", rendered)
        self.assertIn("Command: `` printf `synthetic` ``", rendered)

    def test_render_packet_refuses_invalid_input(self) -> None:
        packet = evidencegate.load_packet(EXAMPLES / "v1-review-ready.json")
        packet["checks"][0]["status"] = "invented"

        with self.assertRaisesRegex(ValueError, "cannot render invalid receipt"):
            evidencegate.render_packet(packet)


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

    def test_verify_cli_can_emit_a_machine_readable_pass(self) -> None:
        head_sha = self.commit_changes({"app.py": "print('synthetic')\n"})
        packet = self.packet_for(head_sha, ["app.py"])
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as receipt_directory:
            receipt_path = Path(receipt_directory) / "receipt.json"
            receipt_path.write_text(json.dumps(packet), encoding="utf-8")
            with redirect_stdout(output):
                result = evidencegate.main(
                    [
                        "verify",
                        str(receipt_path),
                        "--repo",
                        str(self.repo),
                        "--format",
                        "json",
                    ]
                )

        document = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertTrue(document["ok"])
        self.assertTrue(document["repository_checked"])
        self.assertEqual(document["findings"], [])

    def test_legacy_verify_json_reports_that_repository_was_not_checked(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = evidencegate.main(
                [
                    "verify",
                    str(EXAMPLES / "good-run.json"),
                    "--repo",
                    str(self.repo),
                    "--format",
                    "json",
                ]
            )

        document = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertFalse(document["repository_checked"])
        self.assertEqual(
            document["findings"][0]["code"], "receipt_not_verifiable"
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

    def test_git_subprocess_has_a_bounded_timeout(self) -> None:
        with mock.patch.object(
            evidencegate.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["git", "status"], 30),
        ):
            result = evidencegate._run_git(self.repo, ["status", "--porcelain"])

        self.assertEqual(result.returncode, 124)
        self.assertIn("timed out", result.stderr)


if __name__ == "__main__":
    unittest.main()
