#!/usr/bin/env python3
"""Run the public attack corpus for EvidenceGate attestation profile v0."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "attestation" / "v0"
sys.path.insert(0, str(ROOT / "tools"))

from attestation_profile import validate_attestation  # noqa: E402

sys.path.insert(0, str(ROOT))
import evidencegate  # noqa: E402


class ConformanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConformanceError(message)


def run() -> list[str]:
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    require(manifest.get("profile") == "evidencegate_attestation_v0", "bad profile")
    require(isinstance(cases, list) and bool(cases), "cases must be non-empty")
    receipt = ROOT / manifest["receipt"]
    output: list[str] = []
    seen: set[str] = set()
    for case in cases:
        require(isinstance(case, dict), "case must be an object")
        case_id = case.get("id")
        require(isinstance(case_id, str) and bool(case_id), "case id must be text")
        require(case_id not in seen, f"duplicate case id: {case_id}")
        seen.add(case_id)
        statement = evidencegate.load_packet(CORPUS / case["statement"])
        at_time = datetime.strptime(case["at_time"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        errors = validate_attestation(
            statement,
            receipt,
            expected_subject=case["expected_subject"],
            expected_issuer=case["expected_issuer"],
            at_time=at_time,
        )
        if case["expected"] == "pass":
            require(not errors, f"{case_id}: unexpected errors: {errors}")
        else:
            contains = case["contains"]
            require(
                any(contains in error for error in errors),
                f"{case_id}: missing {contains!r} in {errors}",
            )
        output.append(f"PASS attestation {case_id}")
    output.append("PASS attestation_profile_v0")
    return output


def main() -> int:
    try:
        output = run()
    except (OSError, KeyError, TypeError, ValueError, ConformanceError) as exc:
        print(f"FAIL attestation_profile_v0: {exc}")
        return 1
    for line in output:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
