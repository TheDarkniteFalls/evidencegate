#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Adversarial, determinism, and metamorphic checks for the v0 profile."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from evalbraid_contract import validate_path  # noqa: E402


OVERLAY = ROOT / "evalbraid" / "v0" / "conformance" / "adversarial" / "manifest.json"
SCHEMA_SHA256 = "a84b01f2e9e4bc375bfc84e4a644e00dc26d7629fe0de66170df43aa928fe519"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def projection(stage: str, exit_code: int, result: dict[str, object]) -> dict[str, object]:
    return {
        "valid": result["valid"],
        "record_sha256": result["record_sha256"],
        "schema_sha256": result["schema_sha256"],
        "findings": [
            {"code": code, "path": path}
            for code, path in sorted(
                {
                    (item["code"], item["path"])
                    for item in result["findings"]  # type: ignore[union-attr]
                },
                key=lambda item: (item[1], item[0]),
            )
        ],
        "exit_class": exit_code,
        "stage": stage,
    }


class EvaluationProvenanceAdversarialTests(unittest.TestCase):
    def test_four_case_overlay_matches_exact_projections(self) -> None:
        manifest = json.loads(OVERLAY.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["cases"]), 4)
        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                record = OVERLAY.parent / case["record"]
                self.assertEqual(sha256(record), case["record_sha256"])
                actual = projection(*validate_path(record))
                expected = {**case["expected_projection"], "stage": case["expected"]}
                self.assertEqual(actual, expected)

    def test_repeated_selected_results_are_byte_identical(self) -> None:
        fixtures = (
            ROOT / "evalbraid" / "v0" / "conformance" / "positive" / "valid-static-explained.json",
            OVERLAY.parent / "invalid-multiple-semantic-findings.json",
        )
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                first = validate_path(fixture)
                second = validate_path(fixture)
                self.assertEqual(first, second)
                self.assertEqual(
                    json.dumps(first[2], separators=(",", ":")).encode(),
                    json.dumps(second[2], separators=(",", ":")).encode(),
                )

    def test_top_level_reordering_changes_only_record_hash(self) -> None:
        source = ROOT / "evalbraid" / "v0" / "conformance" / "positive" / "valid-static-explained.json"
        original = json.loads(source.read_text(encoding="utf-8"))
        reordered = {key: original[key] for key in reversed(original)}
        with tempfile.TemporaryDirectory(prefix="evalbraid-profile-v0-") as directory:
            changed = Path(directory) / "reordered.json"
            changed.write_text(json.dumps(reordered, indent=2) + "\n", encoding="utf-8")
            original_stage, original_exit, original_result = validate_path(source)
            changed_stage, changed_exit, changed_result = validate_path(changed)
        self.assertEqual((original_stage, original_exit), (changed_stage, changed_exit))
        self.assertNotEqual(original_result["record_sha256"], changed_result["record_sha256"])
        for key in ("valid", "profile", "schema_sha256", "findings"):
            self.assertEqual(original_result[key], changed_result[key])

    def test_schema_remains_pinned(self) -> None:
        self.assertEqual(
            sha256(ROOT / "schemas" / "evalbraid-evaluation-provenance-v0.schema.json"),
            SCHEMA_SHA256,
        )


if __name__ == "__main__":
    unittest.main()
