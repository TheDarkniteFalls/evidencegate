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


EXPECTED_SCHEMA_SHA256 = "5cb28a06a3c012c5c7faa762b1d5e0a7512c13fef2528ff4d66df94329814806"
EXPECTED_SOURCE_HASHES = {
    "valid-static-explained.json": "0026208c6a4a7ec7ab638f8708d15eb16d3596bf8ebf7fc09cdbbf3871d9c741",
    "valid-runtime-unresolved.json": "ff7f95e8fee726b15746474a665e14a6e5e3770955a425dbf19bd3c937bb3f11",
    "valid-integrity-adjudicated.json": "68d8b514607660068932928f32b430bf6300253c99bde3333f5908357603f30f",
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
        self.assertEqual(result["counts"], {"total": 28, "positive": 3, "negative": 25, "passed": 28, "failed": 0})
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

    def test_failure_class_is_attempt_level_and_separate_from_attribution(self) -> None:
        examples = ROOT / "evalbraid" / "v0" / "examples"
        expected = {
            "valid-static-explained.json": ("output_length_exceeded", "agent"),
            "valid-runtime-unresolved.json": ("verifier_result_not_observed", "unknown"),
            "valid-integrity-adjudicated.json": ("answer_mismatch", "agent"),
        }
        for name, (failure_class, attribution) in expected.items():
            with self.subTest(name=name):
                record = json.loads((examples / name).read_text(encoding="utf-8"))
                self.assertEqual(record["verifier_result"]["failure_class"], failure_class)
                self.assertEqual(record["evaluation_judgment"]["causal_attribution"], attribution)

    def test_passed_verifier_requires_and_accepts_null_failure_class(self) -> None:
        source = ROOT / "evalbraid" / "v0" / "conformance" / "positive" / "valid-static-explained.json"
        record = json.loads(source.read_text(encoding="utf-8"))
        record["verifier_result"].update(
            {
                "execution_status": "passed",
                "failure_class": None,
                "exit_status": {"status": "observed", "code": 0},
                "reward": {"status": "observed", "value": 1},
                "first_failure_or_threshold": {
                    "status": "not_applicable",
                    "reason": "Verifier passed; no failure or threshold breach occurred.",
                },
            }
        )
        with tempfile.TemporaryDirectory(prefix="evalbraid-passed-") as directory:
            candidate = Path(directory) / "passed.json"
            candidate.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            stage, exit_code, result = validate_path(candidate)
        self.assertEqual(stage, "pass")
        self.assertEqual(exit_code, 0)
        self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()
