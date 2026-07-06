#!/usr/bin/env python3
"""Validate a small evidence packet for human-reviewed agent work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PASS_STATUSES = {"passed", "skipped"}


def require_text(packet: dict[str, Any], key: str, errors: list[str]) -> None:
    if not isinstance(packet.get(key), str) or not packet[key].strip():
        errors.append(f"{key} must be non-empty text")


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    require_text(packet, "summary", errors)

    commands = packet.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty list")
    else:
        for index, command in enumerate(commands, start=1):
            if not isinstance(command, dict) or not command.get("command") or command.get("result") not in PASS_STATUSES:
                errors.append(f"commands[{index}] needs command plus result passed/skipped")

    files = packet.get("files_touched")
    if not isinstance(files, list) or not all(isinstance(item, str) and item for item in files):
        errors.append("files_touched must be a list of paths")

    tests = packet.get("tests")
    if not isinstance(tests, list) or not tests:
        errors.append("tests must be a non-empty list")
    else:
        for index, test in enumerate(tests, start=1):
            if not isinstance(test, dict) or not test.get("name") or test.get("status") != "passed":
                errors.append(f"tests[{index}] must name a passed check")

    risks = packet.get("risks")
    if not isinstance(risks, list) or not risks:
        errors.append("risks must be a non-empty list, use 'none' when appropriate")

    review = packet.get("human_review")
    if not isinstance(review, dict) or review.get("status") != "approved":
        errors.append("human_review.status must be approved")
    elif not review.get("reviewer"):
        errors.append("human_review.reviewer is required")

    safety = packet.get("public_safety")
    if not isinstance(safety, dict) or safety.get("private_data_reviewed") is not True:
        errors.append("public_safety.private_data_reviewed must be true")
    return errors


def load_packet(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("packet must be a JSON object")
    return data


def self_test() -> None:
    good = {
        "summary": "Added a README and one test.",
        "commands": [{"command": "python3 demo.py --self-test", "result": "passed"}],
        "files_touched": ["README.md", "demo.py"],
        "tests": [{"name": "self-test", "status": "passed"}],
        "risks": ["none"],
        "human_review": {"status": "approved", "reviewer": "maintainer"},
        "public_safety": {"private_data_reviewed": True},
    }
    bad = dict(good)
    bad["human_review"] = {"status": "pending"}
    assert validate_packet(good) == []
    assert validate_packet(bad)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        print("self-test passed")
        return 0
    if not args.path:
        parser.error("path is required unless --self-test is used")

    try:
        packet = load_packet(Path(args.path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Could not load packet: {exc}", file=sys.stderr)
        return 2

    errors = validate_packet(packet)
    if not errors:
        print("PASS EvidenceGate")
        return 0
    print("FAIL EvidenceGate")
    for error in errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
