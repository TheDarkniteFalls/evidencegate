#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression checks for the experimental Evaluation Provenance validator and corpus."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_evalbraid_conformance import run_manifest  # noqa: E402
from evalbraid_contract import (  # noqa: E402
    DEFAULT_SCHEMA,
    _semantic_findings,
    validate_path,
)


EXPECTED_SCHEMA_SHA256 = "a84b01f2e9e4bc375bfc84e4a644e00dc26d7629fe0de66170df43aa928fe519"
EXPECTED_SOURCE_HASHES = {
    "valid-static-explained.json": "2e6a201cf362f1db6d766b9dbda9ec30dc8cbbe4c7a6ebde0297f29dc3f415e3",
    "valid-runtime-unresolved.json": "18c8249d976ae6227427887a5a3ad971c53ca3571bb275561d97519d5dc77de2",
    "valid-integrity-adjudicated.json": "746c8c89dbc13cce00cb5bdaf321a74efddca2fe4feca639d1dca6c3779f7d68",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvaluationProvenanceSlice21Tests(unittest.TestCase):
    def test_reconciled_schema_and_source_example_hashes(self) -> None:
        self.assertEqual(sha256(DEFAULT_SCHEMA), EXPECTED_SCHEMA_SHA256)
        examples = ROOT / "evalbraid" / "v0" / "examples"
        for name, expected in EXPECTED_SOURCE_HASHES.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(examples / name), expected)

    def test_conformance_manifest_passes_offline(self) -> None:
        result = run_manifest()
        self.assertTrue(result["valid"])
        self.assertEqual(result["counts"], {"total": 24, "positive": 3, "negative": 21, "passed": 24, "failed": 0})
        self.assertEqual(result["network_attempts"], 0)
        self.assertTrue(all(result["invariants"].values()))

    def test_result_contract_is_exact_and_deterministic(self) -> None:
        fixture = (
            ROOT
            / "evalbraid"
            / "v0"
            / "conformance"
            / "negative"
            / "invalid-unresolved-reference.json"
        )
        first = validate_path(fixture)
        second = validate_path(fixture)
        self.assertEqual(first, second)
        stage, exit_code, result = first
        self.assertEqual(stage, "semantic_error")
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            set(result),
            {"contract", "valid", "profile", "record_sha256", "schema_sha256", "findings"},
        )
        self.assertEqual(
            result["findings"],
            sorted(result["findings"], key=lambda item: (item["path"], item["code"], item["message"])),
        )

    def test_missing_layer_reaches_semantic_stage(self) -> None:
        negative = ROOT / "evalbraid" / "v0" / "conformance" / "negative"
        stage, exit_code, result = validate_path(negative / "invalid-missing-layer.json")
        self.assertEqual(stage, "semantic_error")
        self.assertEqual(exit_code, 1)
        self.assertIn(
            {"code": "profile_layer_missing", "path": "/source_references"},
            [{"code": item["code"], "path": item["path"]} for item in result["findings"]],
        )

    def test_schema_defensive_self_check_code_remains_implemented(self) -> None:
        fixture = (
            ROOT
            / "evalbraid"
            / "v0"
            / "conformance"
            / "negative"
            / "invalid-self-check-independence.json"
        )
        record = json.loads(fixture.read_text(encoding="utf-8"))
        codes = {finding["code"] for finding in _semantic_findings(record)}
        self.assertIn("profile_self_check_independence_invalid", codes)

    def test_legacy_experimental_profile_identifier_is_rejected(self) -> None:
        source = ROOT / "evalbraid" / "v0" / "conformance" / "positive" / "valid-static-explained.json"
        record = json.loads(source.read_text(encoding="utf-8"))
        record["profile"] = "evidencegate_evaluation_provenance_v0"
        with tempfile.TemporaryDirectory(prefix="evalbraid-legacy-alias-") as directory:
            candidate = Path(directory) / "legacy-profile.json"
            candidate.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            stage, exit_code, result = validate_path(candidate)
        self.assertEqual(stage, "schema_error")
        self.assertEqual(exit_code, 1)
        self.assertIn(
            {"code": "profile_schema_invalid", "path": "/profile"},
            [{"code": item["code"], "path": item["path"]} for item in result["findings"]],
        )

    def test_runtime_source_and_fixture_are_identical_semantic_positives(self) -> None:
        source = ROOT / "evalbraid" / "v0" / "examples" / "valid-runtime-unresolved.json"
        fixture = (
            ROOT
            / "evalbraid"
            / "v0"
            / "conformance"
            / "positive"
            / "valid-runtime-unresolved.json"
        )
        source_stage, _, source_result = validate_path(source)
        fixture_stage, _, fixture_result = validate_path(fixture)
        self.assertEqual(source_stage, "pass")
        self.assertTrue(source_result["valid"])
        self.assertEqual(fixture_stage, "pass")
        self.assertTrue(fixture_result["valid"])
        self.assertEqual(source.read_bytes(), fixture.read_bytes())


if __name__ == "__main__":
    unittest.main()
