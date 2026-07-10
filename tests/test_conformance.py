from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import evidencegate

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # The runtime remains standard-library only.
    Draft202012Validator = None


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "agent-run-receipt-v1.schema.json"
CHECKER = ROOT / "tools" / "check_conformance.py"
EXPECTED_OUTPUT = [
    "PASS conformance valid-minimal",
    "PASS conformance duplicate-key-rejected",
    "PASS conformance unknown-field-rejected",
    "PASS conformance stale-check-rejected",
    "PASS conformance nonpassing-claim-rejected",
    "PASS conformance markdown-neutralized",
    "PASS conformance_v1",
]


class SchemaContractTests(unittest.TestCase):
    def load_schema(self) -> dict:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_schema_top_level_fields_match_runtime_contract(self) -> None:
        schema = self.load_schema()

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), evidencegate.V1_TOP_LEVEL_FIELDS)
        self.assertEqual(
            set(schema["required"]),
            evidencegate.V1_TOP_LEVEL_FIELDS - {"extensions"},
        )

    @unittest.skipIf(Draft202012Validator is None, "install .[test] for meta-validation")
    def test_schema_is_valid_draft_2020_12_and_matches_structural_cases(self) -> None:
        schema = self.load_schema()
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        corpus = ROOT / "conformance" / "v1"

        for name in (
            "valid-minimal.json",
            "valid-adversarial-markdown.json",
            "invalid-stale-check.json",
            "invalid-nonpassing-claim.json",
        ):
            fixture = json.loads((corpus / name).read_text(encoding="utf-8"))
            with self.subTest(name=name):
                self.assertEqual(list(validator.iter_errors(fixture)), [])

        unknown = json.loads(
            (corpus / "invalid-unknown-field.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            any(
                error.validator == "additionalProperties"
                for error in validator.iter_errors(unknown)
            )
        )

    def test_schema_enums_match_runtime_contract(self) -> None:
        properties = self.load_schema()["properties"]

        self.assertEqual(
            set(properties["checks"]["items"]["properties"]["status"]["enum"]),
            evidencegate.V1_CHECK_STATUSES,
        )
        self.assertEqual(
            set(properties["human_review"]["properties"]["status"]["enum"]),
            evidencegate.V1_HUMAN_REVIEW_STATUSES,
        )
        self.assertEqual(
            set(properties["public_safety"]["properties"]["status"]["enum"]),
            evidencegate.V1_PUBLIC_SAFETY_STATUSES,
        )

    def test_schema_nested_fields_match_runtime_contract(self) -> None:
        properties = self.load_schema()["properties"]

        self.assertEqual(
            set(properties["subject"]["properties"]), evidencegate.V1_SUBJECT_FIELDS
        )
        self.assertEqual(
            set(properties["scope"]["properties"]), evidencegate.V1_SCOPE_FIELDS
        )
        self.assertEqual(
            set(properties["checks"]["items"]["properties"]),
            evidencegate.V1_CHECK_FIELDS,
        )
        self.assertEqual(
            set(properties["claims"]["items"]["properties"]),
            evidencegate.V1_CLAIM_FIELDS,
        )


class ConformanceRunnerTests(unittest.TestCase):
    def test_portable_v1_corpus_passes(self) -> None:
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
        self.assertEqual(result.stdout.splitlines(), EXPECTED_OUTPUT)


if __name__ == "__main__":
    unittest.main()
