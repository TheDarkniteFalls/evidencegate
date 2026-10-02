#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the Evaluation Provenance v0 conformance corpus offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
from pathlib import Path
from typing import Any

from evalbraid_contract import CONTRACT as RESULT_CONTRACT
from evalbraid_contract import _strict_object
from evalbraid_contract import validate_path


CONFORMANCE_CONTRACT = "evalbraid_evaluation_provenance_conformance_result_v0"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "evalbraid" / "v0" / "conformance" / "manifest.json"
RESULT_KEYS = {
    "contract",
    "valid",
    "profile",
    "record_sha256",
    "schema_sha256",
    "findings",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _NetworkGuard:
    def __init__(self) -> None:
        self.attempts = 0
        self._originals: dict[str, Any] = {}

    def _deny(self, *_args: Any, **_kwargs: Any) -> None:
        self.attempts += 1
        raise RuntimeError("network access is disabled during conformance validation")

    def __enter__(self) -> "_NetworkGuard":
        self._originals = {
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
            "create_connection": socket.create_connection,
            "getaddrinfo": socket.getaddrinfo,
        }
        socket.socket.connect = self._deny  # type: ignore[method-assign]
        socket.socket.connect_ex = self._deny  # type: ignore[method-assign]
        socket.create_connection = self._deny  # type: ignore[assignment]
        socket.getaddrinfo = self._deny  # type: ignore[assignment]
        return self

    def __exit__(self, *_args: Any) -> None:
        socket.socket.connect = self._originals["connect"]  # type: ignore[method-assign]
        socket.socket.connect_ex = self._originals["connect_ex"]  # type: ignore[method-assign]
        socket.create_connection = self._originals["create_connection"]  # type: ignore[assignment]
        socket.getaddrinfo = self._originals["getaddrinfo"]  # type: ignore[assignment]


def run_manifest(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_strict_object)
    manifest_dir = manifest_path.parent
    schema_path = (manifest_dir / manifest["schema"]["path"]).resolve()
    schema_sha256 = _sha256(schema_path)

    cases = manifest["cases"]
    case_results: list[dict[str, Any]] = []
    with _NetworkGuard() as guard:
        for case in cases:
            record_path = (manifest_dir / case["record"]).resolve()
            actual_sha256 = _sha256(record_path)
            hash_match = actual_sha256 == case["record_sha256"]
            if hash_match:
                stage, exit_code, result = validate_path(record_path, schema_path)
            else:
                stage, exit_code, result = "not_run", 2, {
                    "contract": RESULT_CONTRACT,
                    "valid": False,
                    "profile": manifest["profile"],
                    "record_sha256": actual_sha256,
                    "schema_sha256": schema_sha256,
                    "findings": [],
                }

            findings = [
                {"code": finding["code"], "path": finding["path"]}
                for finding in result["findings"]
            ]
            expected_pair = None
            if "expected_code" in case:
                expected_pair = (case["expected_code"], case.get("expected_path"))
            code_match = True
            if expected_pair is not None:
                expected_code, expected_path = expected_pair
                code_match = any(
                    finding["code"] == expected_code
                    and ("expected_path" not in case or finding["path"] == expected_path)
                    for finding in result["findings"]
                )
            shape_match = set(result) == RESULT_KEYS and result["contract"] == RESULT_CONTRACT
            valid_match = result["valid"] is (case["expected"] == "pass")
            passed = all(
                (
                    hash_match,
                    stage == case["expected"],
                    code_match,
                    shape_match,
                    valid_match,
                    result["schema_sha256"] == schema_sha256,
                )
            )
            case_results.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "expected_stage": case["expected"],
                    "actual_stage": stage,
                    "exit_code": exit_code,
                    "record_sha256": actual_sha256,
                    "artifact_hash_match": hash_match,
                    "result_shape_match": shape_match,
                    "findings": findings,
                }
            )

    positive_count = sum(case["expected"] == "pass" for case in cases)
    negative_count = len(cases) - positive_count
    passed_count = sum(case["passed"] for case in case_results)
    case_metadata_complete = all(
        {"id", "record", "record_sha256", "expected", "mutation"} <= set(case)
        and case["expected"] in {"pass", "load_error", "schema_error", "semantic_error"}
        and (
            (case["expected"] == "pass" and "expected_code" not in case and "base" not in case)
            or (case["expected"] != "pass" and {"expected_code", "base"} <= set(case))
        )
        for case in cases
    )
    record_paths_confined = all(
        (manifest_dir / case["record"]).resolve().is_relative_to(manifest_dir)
        for case in cases
    )
    source_examples = manifest.get("source_examples", [])
    source_example_hashes_match = len(source_examples) == 3 and all(
        _sha256((manifest_dir / item["source"]).resolve()) == item["source_sha256"]
        and _sha256((manifest_dir / item["fixture"]).resolve()) == item["fixture_sha256"]
        for item in source_examples
    )
    invariants = {
        "manifest_version": manifest.get("manifest_version")
        == "evalbraid_evaluation_provenance_conformance_v0",
        "result_contract": manifest.get("result_contract") == RESULT_CONTRACT,
        "case_ids_unique": len({case["id"] for case in cases}) == len(cases),
        "case_count_29": len(cases) == 29,
        "positive_count_3": positive_count == 3,
        "negative_count_26": negative_count == 26,
        "case_metadata_complete": case_metadata_complete,
        "record_paths_confined": record_paths_confined,
        "schema_hash_match": schema_sha256 == manifest["schema"]["sha256"],
        "source_example_hashes_match": source_example_hashes_match,
        "network_attempts_zero": guard.attempts == 0,
    }
    valid = passed_count == len(case_results) and all(invariants.values())
    return {
        "contract": CONFORMANCE_CONTRACT,
        "valid": valid,
        "manifest_sha256": manifest_sha256,
        "schema_sha256": schema_sha256,
        "counts": {
            "total": len(case_results),
            "positive": positive_count,
            "negative": negative_count,
            "passed": passed_count,
            "failed": len(case_results) - passed_count,
        },
        "network_attempts": guard.attempts,
        "invariants": invariants,
        "cases": case_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        result = run_manifest(args.manifest)
    except Exception as exc:
        print(f"conformance tool error: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(result, separators=(",", ":")))
    else:
        counts = result["counts"]
        print(
            f"{'PASS' if result['valid'] else 'FAIL'}: "
            f"{counts['passed']}/{counts['total']} cases; "
            f"network attempts={result['network_attempts']}"
        )
        for case in result["cases"]:
            if not case["passed"]:
                print(f"FAIL {case['id']}: {case['actual_stage']} {case['findings']}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
