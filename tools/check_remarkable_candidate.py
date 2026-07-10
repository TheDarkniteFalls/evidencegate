#!/usr/bin/env python3
"""Run every maintainer-controlled EvidenceGate remarkable-candidate gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 180


def _run(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
    )
    combined = result.stdout + result.stderr
    return {
        "command": command,
        "returncode": result.returncode,
        "output_sha256": hashlib.sha256(combined.encode()).hexdigest(),
        "output": combined,
    }


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    if sys.version_info < (3, 10):
        print("FAIL remarkable candidate: Python 3.10 or newer is required")
        return 1
    if args.report and args.report.resolve().is_relative_to(ROOT.resolve()):
        print("FAIL remarkable candidate: write evidence reports outside the repository")
        return 1
    node = shutil.which("node")
    if node is None:
        print("FAIL remarkable candidate: Node is required for cross-language proof")
        return 1
    commands = [
        ("reference-self-test", [sys.executable, "-B", "evidencegate.py", "--self-test"]),
        ("unit-tests", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("python-conformance", [sys.executable, "-B", "tools/check_conformance.py"]),
        ("node-conformance", [node, "replication/node/check-conformance.mjs"]),
        ("reference-lifecycle", [sys.executable, "-B", "examples/run-v1-reference.py"]),
        ("failure-semantics", [sys.executable, "-B", "examples/check_failure_semantics.py"]),
        ("attestation-attacks", [sys.executable, "-B", "tools/check_attestation_conformance.py"]),
        ("reviewer-study-contract", [sys.executable, "-B", "tools/check_reviewer_study.py"]),
    ]
    try:
        head = _git("rev-parse", "HEAD")
        dirty = bool(_git("status", "--porcelain=v1", "--untracked-files=all"))
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"FAIL remarkable candidate: cannot inspect Git state: {exc}")
        return 1
    if dirty and not args.allow_dirty:
        print(
            "FAIL remarkable candidate: work tree is dirty; "
            "use --allow-dirty only during development"
        )
        return 1

    schema_results: list[dict[str, str]] = []
    try:
        for relative in (
            "schemas/agent-run-receipt-v1.schema.json",
            "schemas/evidencegate-attestation-v0.schema.json",
        ):
            value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            if value.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                raise ValueError(f"{relative}: unexpected schema dialect")
            schema_results.append({"path": relative, "status": "passed"})
            print(f"PASS remarkable gate schema {relative}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL remarkable candidate schema gate: {exc}")
        return 1

    results: list[dict[str, Any]] = []
    for name, command in commands:
        try:
            result = _run(command)
        except subprocess.TimeoutExpired:
            print(f"FAIL remarkable gate {name}: timed out after {TIMEOUT_SECONDS}s")
            return 1
        results.append(
            {
                "name": name,
                **{key: value for key, value in result.items() if key != "output"},
            }
        )
        if result["returncode"] != 0:
            print(f"FAIL remarkable gate {name}")
            print(result["output"], end="")
            return 1
        print(f"PASS remarkable gate {name}")

    report = {
        "profile": "evidencegate_remarkable_candidate_v0",
        "generated_at": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "git_head": head,
        "dirty_work_tree": dirty,
        "dirty_override_used": bool(dirty and args.allow_dirty),
        "eligible_for_candidate_claim": not dirty,
        "environment": {
            "python": platform.python_version(),
            "node": _run([node, "--version"])["output"].strip(),
            "platform": platform.platform(),
        },
        "schemas": schema_results,
        "gates": results,
        "claim_boundary": {
            "candidate_engineering": "passed" if not dirty else "development_pass_only",
            "authenticated_record": "not_claimed",
            "measured_reviewer_effect": "not_claimed",
            "independent_replication": "not_claimed",
        },
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"PASS remarkable evidence report {args.report}")
    suffix = " (DIRTY DEVELOPMENT RUN)" if dirty else ""
    print(f"PASS EvidenceGate remarkable candidate gates at {head}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
