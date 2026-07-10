from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:
    Draft202012Validator = None


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "evidencegate-attestation-v0.schema.json"
CHECKER = ROOT / "tools" / "check_attestation_conformance.py"
sys.path.insert(0, str(ROOT / "tools"))

import attestation_profile  # noqa: E402
from create_attestation_statement import create_statement  # noqa: E402


class AttestationProfileTests(unittest.TestCase):
    def test_schema_fields_match_runtime_profile(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

        self.assertEqual(set(schema["properties"]), attestation_profile.TOP_FIELDS)
        predicate = schema["properties"]["predicate"]
        self.assertEqual(
            set(predicate["properties"]), attestation_profile.PREDICATE_FIELDS
        )
        self.assertEqual(
            set(predicate["properties"]["receipt"]["properties"]),
            attestation_profile.RECEIPT_FIELDS,
        )

    @unittest.skipIf(Draft202012Validator is None, "install .[test] for meta-validation")
    def test_schema_is_valid_and_accepts_the_unsigned_contract_fixture(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        statement = json.loads(
            (ROOT / "attestation" / "v0" / "valid-unsigned.json").read_text(
                encoding="utf-8"
            )
        )

        Draft202012Validator.check_schema(schema)
        self.assertEqual(
            list(Draft202012Validator(schema).iter_errors(statement)), []
        )

    def test_attack_corpus_passes_and_labels_only_the_contract_valid(self) -> None:
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
        self.assertIn("PASS attestation tampered-receipt-rejected", result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith("PASS attestation_profile_v0"))

    def test_generator_round_trips_a_valid_receipt_without_authentication_claim(self) -> None:
        receipt = ROOT / "conformance" / "v1" / "valid-minimal.json"
        issued_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        subject = "git+https://github.com/TheDarkniteFalls/evidencegate"
        issuer = "https://example.invalid/synthetic-workflow"

        statement = create_statement(
            receipt,
            subject_name=subject,
            claimed_issuer=issuer,
            issued_at=issued_at,
            valid_for_minutes=60,
        )

        self.assertEqual(
            attestation_profile.validate_attestation(
                statement,
                receipt,
                expected_subject=subject,
                expected_issuer=issuer,
                at_time=issued_at,
            ),
            [],
        )
        self.assertNotIn("signature", json.dumps(statement).lower())

    def test_generator_cli_writes_only_an_unsigned_statement(self) -> None:
        receipt = ROOT / "conformance" / "v1" / "valid-minimal.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "statement.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "tools" / "create_attestation_statement.py"),
                    str(receipt),
                    "--subject",
                    "git+https://github.com/TheDarkniteFalls/evidencegate",
                    "--claimed-issuer",
                    "https://example.invalid/synthetic-workflow",
                    "--issued-at",
                    "2030-01-01T00:00:00Z",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertIn("UNAUTHENTICATED", result.stdout)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["_type"],
                attestation_profile.STATEMENT_TYPE,
            )


if __name__ == "__main__":
    unittest.main()
