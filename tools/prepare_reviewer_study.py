#!/usr/bin/env python3
"""Create blinded, counterbalanced EvidenceGate reviewer-study packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "study" / "v0" / "scenarios.json"
sys.path.insert(0, str(ROOT))

import evidencegate  # noqa: E402


CONDITIONS = ("transcript_only", "receipt_assisted")
PARTICIPANT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class StudyError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StudyError(message)


def load_scenarios(path: Path = SCENARIOS) -> dict[str, Any]:
    study = evidencegate.load_packet(path)
    _require(
        study.get("study_version") == "evidencegate_reviewer_study_v0",
        "unsupported study version",
    )
    scenarios = study.get("scenarios")
    reason_codes = study.get("reason_codes")
    _require(isinstance(scenarios, list) and len(scenarios) >= 2, "need scenarios")
    _require(len(scenarios) % 2 == 0, "scenario count must be even")
    _require(isinstance(reason_codes, list) and bool(reason_codes), "need reason codes")
    seen: set[str] = set()
    for scenario in scenarios:
        _require(isinstance(scenario, dict), "scenario must be an object")
        scenario_id = scenario.get("id")
        _require(isinstance(scenario_id, str) and bool(scenario_id), "bad scenario id")
        _require(scenario_id not in seen, f"duplicate scenario id: {scenario_id}")
        seen.add(scenario_id)
        truth = scenario.get("ground_truth")
        _require(isinstance(truth, dict), f"{scenario_id}: missing ground truth")
        _require(truth.get("decision") in {"accept", "reject"}, f"{scenario_id}: bad decision")
        expected_reasons = truth.get("reason_codes")
        _require(
            isinstance(expected_reasons, list)
            and bool(expected_reasons)
            and set(expected_reasons) <= set(reason_codes),
            f"{scenario_id}: bad reason codes",
        )
        _require(
            isinstance(scenario.get("transcript"), list)
            and all(isinstance(line, str) and line.strip() for line in scenario["transcript"]),
            f"{scenario_id}: transcript must contain text",
        )
        receipt_path = scenario.get("receipt")
        _require(isinstance(receipt_path, str), f"{scenario_id}: receipt path required")
        resolved_receipt = (ROOT / receipt_path).resolve()
        _require(
            resolved_receipt.is_relative_to(ROOT.resolve()),
            f"{scenario_id}: receipt must stay inside the repository",
        )
        _require(resolved_receipt.is_file(), f"{scenario_id}: missing receipt")
    return study


def _blind_id(seed: str, participant: str, scenario_id: str) -> str:
    value = hashlib.sha256(f"{seed}|{participant}|{scenario_id}".encode()).hexdigest()
    return f"case-{value[:10]}"


def _presentation_key(seed: str, participant: str, scenario_id: str) -> str:
    return hashlib.sha256(
        f"order|{seed}|{participant}|{scenario_id}".encode()
    ).hexdigest()


def _gate_report(receipt_path: Path) -> dict[str, Any]:
    receipt = evidencegate.load_packet(receipt_path)
    validation_errors = evidencegate.validate_packet(receipt)
    report: dict[str, Any] = {
        "validation": "failed" if validation_errors else "passed",
        "validation_errors": validation_errors,
        "repository_verification": "not_run_for_synthetic_study_case",
    }
    if not validation_errors and evidencegate.receipt_version(receipt) == "v1":
        readiness = evidencegate.review_readiness_errors(receipt)
        report["review_readiness"] = "blocked" if readiness else "ready"
        report["review_readiness_errors"] = readiness
        report["rendered_receipt"] = evidencegate.render_packet(receipt)
    else:
        report["review_readiness"] = "not_evaluated"
        report["review_readiness_errors"] = []
    report["receipt"] = receipt
    return report


def build_materials(
    study: dict[str, Any], *, participant: str, arm: str, seed: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _require(
        PARTICIPANT_ID.fullmatch(participant) is not None,
        "participant id must be 1-64 letters, numbers, '.', '_', or '-'",
    )
    _require(arm in {"A", "B"}, "arm must be A or B")
    _require(bool(seed), "seed must be non-empty")
    ordered = sorted(study["scenarios"], key=lambda item: item["id"])
    cases: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    for index, scenario in enumerate(ordered):
        assisted = index % 2 == 1
        if arm == "B":
            assisted = not assisted
        condition = CONDITIONS[1] if assisted else CONDITIONS[0]
        blind_id = _blind_id(seed, participant, scenario["id"])
        case: dict[str, Any] = {
            "case_id": blind_id,
            "condition": condition,
            "transcript": scenario["transcript"],
        }
        if assisted:
            case["evidencegate"] = _gate_report(ROOT / scenario["receipt"])
        cases.append(case)
        answers.append(
            {
                "case_id": blind_id,
                "condition": condition,
                "scenario_id": scenario["id"],
                "category": scenario["category"],
                "expected_decision": scenario["ground_truth"]["decision"],
                "expected_reason_codes": scenario["ground_truth"]["reason_codes"],
            }
        )
    order = {
        case["case_id"]: _presentation_key(
            seed,
            participant,
            next(item["scenario_id"] for item in answers if item["case_id"] == case["case_id"]),
        )
        for case in cases
    }
    cases.sort(key=lambda item: order[item["case_id"]])
    answers.sort(key=lambda item: order[item["case_id"]])
    packet = {
        "study_version": study["study_version"],
        "participant_id": participant,
        "arm": arm,
        "instructions": [
            "Review each case using only the supplied material.",
            "Choose accept only when the change is justified by the available evidence.",
            "Do not inspect the coordinator key or study source while participating.",
        ],
        "reason_codes": study["reason_codes"],
        "cases": cases,
    }
    response = {
        "study_version": study["study_version"],
        "participant_id": participant,
        "responses": [
            {
                "case_id": case["case_id"],
                "decision": None,
                "reason_codes": [],
                "accept_probability": None,
                "decision_seconds": None,
            }
            for case in cases
        ],
    }
    key = {
        "study_version": study["study_version"],
        "participant_id": participant,
        "arm": arm,
        "seed": seed,
        "reason_codes": study["reason_codes"],
        "answers": answers,
    }
    return packet, response, key


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant", required=True)
    parser.add_argument("--arm", choices=("A", "B"), required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--response-template", type=Path, required=True)
    parser.add_argument("--coordinator-key", type=Path, required=True)
    parser.add_argument("--seed", default="evidencegate-public-study-v0")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        destinations = {
            args.packet.resolve(),
            args.response_template.resolve(),
            args.coordinator_key.resolve(),
        }
        _require(len(destinations) == 3, "packet, response, and key paths must differ")
        materials = build_materials(
            load_scenarios(), participant=args.participant, arm=args.arm, seed=args.seed
        )
        _write_json(args.packet, materials[0])
        _write_json(args.response_template, materials[1])
        _write_json(args.coordinator_key, materials[2])
    except (OSError, ValueError, StudyError) as exc:
        print(f"FAIL reviewer study preparation: {exc}")
        return 1
    print(f"PASS reviewer study packet {args.participant} arm {args.arm}")
    print("KEEP coordinator key separate from the participant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
