#!/usr/bin/env python3
"""Run the portable EvidenceGate v1 conformance corpus."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "conformance" / "v1"
MANIFEST = CORPUS / "manifest.json"
sys.path.insert(0, str(ROOT))

import evidencegate  # noqa: E402


class ConformanceError(RuntimeError):
    """Raised when an implementation result disagrees with the corpus."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConformanceError(message)


def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConformanceError("manifest must be a JSON object")
    if value.get("schema_version") != "evidencegate_conformance_v1":
        raise ConformanceError("unsupported conformance manifest version")
    if value.get("cli_result_contract") != evidencegate.CLI_RESULT_CONTRACT:
        raise ConformanceError("unsupported CLI result contract version")
    if not isinstance(value.get("cases"), list) or not value["cases"]:
        raise ConformanceError("manifest cases must be a non-empty list")
    return value


def check_case(case: dict[str, Any]) -> None:
    case_id = case.get("id")
    require(isinstance(case_id, str) and bool(case_id), "case id must be text")
    receipt_name = case.get("receipt")
    require(
        isinstance(receipt_name, str) and bool(receipt_name),
        f"{case_id}: receipt must be text",
    )
    expected = case.get("expected")
    require(
        expected in {"pass", "load_error", "validation_error"},
        f"{case_id}: unsupported expectation",
    )
    receipt_path = CORPUS / receipt_name

    try:
        packet = evidencegate.load_packet(receipt_path)
    except (OSError, ValueError) as exc:
        require(expected == "load_error", f"{case_id}: unexpected load error: {exc}")
        expected_code = case.get("expected_code")
        require(
            not expected_code
            or evidencegate.finding_code(str(exc), phase="load") == expected_code,
            f"{case_id}: load error code did not match {expected_code!r}",
        )
        contains = case.get("contains")
        require(
            not contains or str(contains) in str(exc),
            f"{case_id}: load error did not contain {contains!r}: {exc}",
        )
        return

    require(expected != "load_error", f"{case_id}: expected a load error")
    errors = evidencegate.validate_packet(packet)
    if expected == "validation_error":
        require(bool(errors), f"{case_id}: expected a validation error")
        expected_code = case.get("expected_code")
        codes = {
            evidencegate.finding_code(error, phase="validation") for error in errors
        }
        require(
            not expected_code or expected_code in codes,
            f"{case_id}: validation codes did not contain {expected_code!r}: {codes}",
        )
        contains = case.get("contains")
        require(
            not contains or any(str(contains) in error for error in errors),
            f"{case_id}: validation errors did not contain {contains!r}: {errors}",
        )
        return

    require(not errors, f"{case_id}: unexpected validation errors: {errors}")
    render_contract = case.get("render")
    if render_contract is None:
        return
    require(isinstance(render_contract, dict), f"{case_id}: render must be an object")
    rendered = evidencegate.render_packet(packet)
    heading = render_contract.get("heading")
    heading_count = render_contract.get("heading_count")
    require(
        isinstance(heading, str) and isinstance(heading_count, int),
        f"{case_id}: render heading contract is invalid",
    )
    require(
        rendered.count(heading) == heading_count,
        f"{case_id}: expected {heading_count} occurrences of {heading!r}",
    )
    forbidden = render_contract.get("forbidden", [])
    require(isinstance(forbidden, list), f"{case_id}: render forbidden must be a list")
    for value in forbidden:
        require(
            isinstance(value, str) and value not in rendered,
            f"{case_id}: rendered output contains forbidden structure {value!r}",
        )


def run_conformance() -> list[str]:
    manifest = load_manifest()
    output: list[str] = []
    seen: set[str] = set()
    for raw_case in manifest["cases"]:
        require(isinstance(raw_case, dict), "every case must be an object")
        case_id = raw_case.get("id")
        require(isinstance(case_id, str), "case id must be text")
        require(case_id not in seen, f"duplicate conformance case id: {case_id}")
        seen.add(case_id)
        check_case(raw_case)
        output.append(f"PASS conformance {case_id}")
    output.append("PASS conformance_v1")
    return output


def main() -> int:
    try:
        output = run_conformance()
    except (OSError, ValueError, ConformanceError) as exc:
        print(f"FAIL conformance_v1: {exc}")
        return 1
    for line in output:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
