#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the read-only experimental profile gate; Linux is not a prerequisite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


CONTRACT = "evalbraid_evaluation_provenance_experimental_gate_v0"
STATUS_CODE = "experimental_author_tested_macos_linux_untested_review_requested"
ROOT = Path(__file__).resolve().parents[1]
PROFILE_MANIFEST = ROOT / "evalbraid" / "v0" / "artifact-manifest.json"
CORE_MANIFEST = ROOT / "evalbraid" / "v0" / "conformance" / "manifest.json"
OVERLAY_MANIFEST = CORE_MANIFEST.parent / "adversarial" / "manifest.json"
PYTHON_CONFORMANCE = ROOT / "tools" / "check_evalbraid_conformance.py"
PYTHON_VALIDATOR = ROOT / "tools" / "evalbraid_contract.py"
NODE_ROOT = ROOT / "replication" / "node" / "evalbraid-v0"
NODE_CONFORMANCE = NODE_ROOT / "check-conformance.mjs"
NODE_VALIDATOR = NODE_ROOT / "validate-record.mjs"
NODE_TESTS = NODE_ROOT / "test-consumer.mjs"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)


def run(command: list[str], env: dict[str, str], allowed: set[int] = {0}) -> dict[str, Any]:
    completed = subprocess.run(command, capture_output=True, check=False, env=env, cwd=ROOT)
    result: dict[str, Any] = {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "passed": completed.returncode in allowed,
    }
    if completed.stdout:
        try:
            result["json"] = json.loads(completed.stdout.decode("utf-8"), object_pairs_hook=strict_object)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            result["stdout_text"] = completed.stdout.decode("utf-8", errors="replace")
    if completed.stderr:
        result["stderr_text"] = completed.stderr.decode("utf-8", errors="replace")
    result["stdout_bytes"] = completed.stdout
    return result


def public_view(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"stdout_bytes", "json"}}


def confined_profile_path(relative: str) -> Path:
    if not relative or relative.startswith("/") or "\\" in relative:
        raise ValueError(f"invalid profile path: {relative!r}")
    path = ROOT / relative
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise ValueError(f"profile path escapes repository root: {relative!r}")
    return path


def verify_profile_manifest() -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    manifest = load_json(PROFILE_MANIFEST)
    entries = manifest.get("files", [])
    seen: set[str] = set()
    set_items: list[str] = []
    for index, item in enumerate(entries):
        relative = item.get("path")
        if not isinstance(relative, str):
            findings.append({"code": "profile_manifest_path_invalid", "path": f"/files/{index}/path", "message": "path must be a string"})
            continue
        if relative in seen:
            findings.append({"code": "profile_manifest_path_duplicate", "path": f"/files/{index}/path", "message": "path is duplicated"})
            continue
        seen.add(relative)
        try:
            path = confined_profile_path(relative)
        except ValueError as exc:
            findings.append({"code": "profile_manifest_path_invalid", "path": f"/files/{index}/path", "message": str(exc)})
            continue
        if path.is_symlink():
            findings.append({"code": "profile_manifest_symlink", "path": f"/files/{index}/path", "message": "symlinks are not allowed"})
            continue
        if not path.is_file():
            findings.append({"code": "profile_manifest_file_missing", "path": f"/files/{index}/path", "message": "file is missing"})
            continue
        actual_hash = sha256(path)
        actual_size = path.stat().st_size
        if actual_hash != item.get("sha256"):
            findings.append({"code": "profile_manifest_hash_mismatch", "path": f"/files/{index}/sha256", "message": "file SHA-256 does not match"})
        if actual_size != item.get("size_bytes"):
            findings.append({"code": "profile_manifest_size_mismatch", "path": f"/files/{index}/size_bytes", "message": "file size does not match"})
        set_items.append(f"{relative}\0{actual_hash}\n")
    file_set = sha256_bytes("".join(sorted(set_items)).encode("utf-8"))
    if len(entries) != manifest.get("file_count"):
        findings.append({"code": "profile_manifest_count_mismatch", "path": "/file_count", "message": "file count does not match entries"})
    if file_set != manifest.get("file_set_sha256"):
        findings.append({"code": "profile_manifest_set_mismatch", "path": "/file_set_sha256", "message": "file-set SHA-256 does not match"})
    findings.sort(key=lambda item: (item["path"], item["code"]))
    return {
        "valid": not findings,
        "manifest_sha256": sha256(PROFILE_MANIFEST),
        "file_set_sha256": file_set,
        "checked_file_count": len(seen),
    }, findings


def snapshot_profile() -> tuple[str, int]:
    manifest = load_json(PROFILE_MANIFEST)
    values = [("evalbraid/v0/artifact-manifest.json", sha256(PROFILE_MANIFEST))]
    for item in manifest["files"]:
        path = confined_profile_path(item["path"])
        values.append((item["path"], sha256(path)))
    payload = "".join(f"{path}\0{digest}\n" for path, digest in sorted(values)).encode("utf-8")
    return sha256_bytes(payload), len(values)


def canonical_projection(stage: str, exit_code: int, result: dict[str, Any]) -> dict[str, Any]:
    pairs = {(item["code"], item["path"]) for item in result["findings"]}
    return {
        "valid": result["valid"],
        "record_sha256": result["record_sha256"],
        "schema_sha256": result["schema_sha256"],
        "findings": [
            {"code": code, "path": path}
            for code, path in sorted(pairs, key=lambda item: (item[1], item[0]))
        ],
        "exit_class": exit_code,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--node-env", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    findings: list[dict[str, str]] = []
    gates: dict[str, Any] = {}
    cross_consumer: dict[str, Any] = {}
    environment_failure = False
    # Preserve a virtual-environment interpreter path instead of resolving its
    # symlink to the base runtime, which would discard the venv dependency set.
    python = Path(args.python).expanduser().absolute()
    node = Path(args.node).expanduser().resolve() if args.node else None
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if args.node_env:
        env["EVALBRAID_NODE_ENV"] = str(args.node_env.expanduser().resolve())

    required = [PROFILE_MANIFEST, python, CORE_MANIFEST, OVERLAY_MANIFEST, NODE_CONFORMANCE, NODE_TESTS]
    if node is not None:
        required.append(node)
    missing = [str(path) for path in required if not path.exists()]
    if node is None or missing:
        findings.append({"code": "experimental_gate_environment_missing", "path": "/environment", "message": "missing required runtime or artifact: " + ", ".join(missing or ["node"])})
        environment_failure = True

    pre_hash = None
    pre_count = None
    try:
        if not environment_failure:
            manifest_result, manifest_findings = verify_profile_manifest()
            gates["profile_manifest"] = manifest_result
            findings.extend(manifest_findings)
            pre_hash, pre_count = snapshot_profile()

            python_core = run([str(python), "-B", str(PYTHON_CONFORMANCE), "--json"], env)
            python_json = python_core.get("json", {})
            python_ok = python_core["passed"] and python_json.get("valid") is True and python_json.get("counts") == {"total": 24, "positive": 3, "negative": 21, "passed": 24, "failed": 0} and python_json.get("network_attempts") == 0
            gates["python_core"] = {**public_view(python_core), "valid": python_ok}
            if not python_ok:
                findings.append({"code": "experimental_gate_python_core_failed", "path": "/gates/python_core", "message": "Python core conformance failed"})

            python_tests = run([str(python), "-B", "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", "test_evalbraid*.py", "-v"], env)
            gates["python_tests"] = {**public_view(python_tests), "valid": python_tests["passed"]}
            if not python_tests["passed"]:
                findings.append({"code": "experimental_gate_python_tests_failed", "path": "/gates/python_tests", "message": "Python profile tests failed"})

            node_core = run([str(node), str(NODE_CONFORMANCE), "--json"], env)  # type: ignore[arg-type]
            node_json = node_core.get("json", {})
            node_ok = node_core["passed"] and node_json.get("valid") is True and node_json.get("counts", {}).get("core") == {"total": 24, "positive": 3, "negative": 21, "passed": 24} and node_json.get("counts", {}).get("overlay") == {"total": 4, "passed": 4} and node_json.get("network_attempts") == 0
            gates["node_core_and_adversarial"] = {**public_view(node_core), "valid": node_ok}
            if not node_ok:
                findings.append({"code": "experimental_gate_node_conformance_failed", "path": "/gates/node_core_and_adversarial", "message": "Node conformance failed"})

            node_tests = run([str(node), str(NODE_TESTS)], env)  # type: ignore[arg-type]
            gates["node_tests"] = {**public_view(node_tests), "valid": node_tests["passed"]}
            if not node_tests["passed"]:
                findings.append({"code": "experimental_gate_node_tests_failed", "path": "/gates/node_tests", "message": "Node tests failed"})

            node_cases = {item["id"]: item for item in node_json.get("cases", [])}
            core_mismatches: list[str] = []
            for case in python_json.get("cases", []):
                expected = {
                    "valid": case["actual_stage"] == "pass",
                    "record_sha256": case["record_sha256"],
                    "schema_sha256": python_json.get("schema_sha256"),
                    "findings": sorted(case["findings"], key=lambda item: (item["path"], item["code"])),
                    "exit_class": case["exit_code"],
                }
                node_case = node_cases.get(case["id"])
                if node_case is None or node_case.get("projection") != expected:
                    core_mismatches.append(case["id"])
            cross_consumer["core"] = {"total": 24, "matched": 24 - len(core_mismatches), "mismatches": core_mismatches}
            if core_mismatches:
                findings.append({"code": "experimental_gate_cross_consumer_mismatch", "path": "/cross_consumer/core", "message": "core projection mismatch: " + ", ".join(core_mismatches)})

            overlay = load_json(OVERLAY_MANIFEST)
            overlay_mismatches: list[str] = []
            for case in overlay["cases"]:
                record = OVERLAY_MANIFEST.parent / case["record"]
                expected_exit = case["expected_projection"]["exit_class"]
                python_case = run([str(python), "-B", str(PYTHON_VALIDATOR), str(record), "--json"], env, {expected_exit})
                python_result = python_case.get("json", {})
                node_case = node_cases.get(case["id"])
                if not python_case["passed"] or "findings" not in python_result or canonical_projection(case["expected"], python_case["exit_code"], python_result) != case["expected_projection"] or node_case is None or node_case.get("projection") != case["expected_projection"]:
                    overlay_mismatches.append(case["id"])
            cross_consumer["adversarial"] = {"total": 4, "matched": 4 - len(overlay_mismatches), "mismatches": overlay_mismatches}
            if overlay_mismatches:
                findings.append({"code": "experimental_gate_adversarial_mismatch", "path": "/cross_consumer/adversarial", "message": "adversarial projection mismatch: " + ", ".join(overlay_mismatches)})

            selected = (
                (ROOT / "evalbraid" / "v0" / "conformance" / "positive" / "valid-static-explained.json", 0),
                (OVERLAY_MANIFEST.parent / "invalid-multiple-semantic-findings.json", 1),
            )
            deterministic = True
            deterministic_cases: list[dict[str, Any]] = []
            for record, expected_exit in selected:
                python_runs = [run([str(python), "-B", str(PYTHON_VALIDATOR), str(record), "--json"], env, {expected_exit}) for _ in range(2)]
                node_runs = [run([str(node), str(NODE_VALIDATOR), str(record), "--json"], env, {expected_exit}) for _ in range(2)]  # type: ignore[arg-type]
                same = python_runs[0]["stdout_bytes"] == python_runs[1]["stdout_bytes"] == node_runs[0]["stdout_bytes"] == node_runs[1]["stdout_bytes"]
                deterministic = deterministic and same and all(item["passed"] for item in [*python_runs, *node_runs])
                deterministic_cases.append({"record": str(record.relative_to(ROOT)), "byte_identical": same, "output_sha256": python_runs[0]["stdout_sha256"]})
            gates["deterministic_selected_outputs"] = {"valid": deterministic, "cases": deterministic_cases}
            if not deterministic:
                findings.append({"code": "experimental_gate_output_nondeterministic", "path": "/gates/deterministic_selected_outputs", "message": "selected Python and Node outputs differ"})

            post_hash, post_count = snapshot_profile()
            unchanged = pre_hash == post_hash and pre_count == post_count
            gates["profile_immutability"] = {"valid": unchanged, "pre_sha256": pre_hash, "post_sha256": post_hash, "file_count": post_count}
            if not unchanged:
                findings.append({"code": "experimental_gate_profile_modified", "path": "/gates/profile_immutability", "message": "profile files changed during validation"})
    except Exception as exc:
        findings.append({"code": "experimental_gate_tool_error", "path": "/gate", "message": str(exc)})
        environment_failure = True

    findings.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    result = {
        "contract": CONTRACT,
        "valid": not findings,
        "status": STATUS_CODE,
        "environment": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": str(python),
            "node": str(node) if node else None,
            "node_environment": env.get("EVALBRAID_NODE_ENV", str(NODE_ROOT)),
        },
        "gates": gates,
        "cross_consumer": cross_consumer,
        "claims": {
            "linux_portability": "not_tested",
            "independent_review": "not_completed",
            "authentication": "not_provided",
            "stable_evidencegate_v1": "unchanged_by_profile",
        },
        "findings": findings,
    }
    if args.as_json:
        print(json.dumps(result, separators=(",", ":")))
    else:
        print(f"{'PASS' if result['valid'] else 'FAIL'} experimental profile gate; status={STATUS_CODE}")
        for finding in findings:
            print(f"{finding['code']} {finding['path']}: {finding['message']}")
    if environment_failure:
        return 2
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
