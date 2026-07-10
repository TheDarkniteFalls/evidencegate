#!/usr/bin/env python3
"""Score real EvidenceGate reviewer-study responses descriptively."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import evidencegate  # noqa: E402


class ScoringError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScoringError(message)


def _load(path: Path) -> dict[str, Any]:
    return evidencegate.load_packet(path)


def score_pair(key: dict[str, Any], response: dict[str, Any]) -> list[dict[str, Any]]:
    _require(key.get("study_version") == "evidencegate_reviewer_study_v0", "bad key version")
    _require(response.get("study_version") == key["study_version"], "version mismatch")
    participant = key.get("participant_id")
    arm = key.get("arm")
    _require(isinstance(participant, str) and bool(participant), "participant required")
    _require(arm in {"A", "B"}, "key arm must be A or B")
    _require(response.get("participant_id") == participant, "participant mismatch")
    answers = key.get("answers")
    responses = response.get("responses")
    allowed_reasons = key.get("reason_codes")
    _require(isinstance(answers, list) and isinstance(responses, list), "missing answers")
    _require(
        isinstance(allowed_reasons, list)
        and bool(allowed_reasons)
        and all(isinstance(reason, str) for reason in allowed_reasons),
        "key reason codes are invalid",
    )
    _require(len(allowed_reasons) == len(set(allowed_reasons)), "duplicate key reason code")
    _require(len(answers) == 12, "reviewer study v0 requires exactly 12 answers")
    for answer in answers:
        _require(isinstance(answer, dict), "answer must be an object")
        _require(
            isinstance(answer.get("case_id"), str) and bool(answer["case_id"]),
            "answer case id must be text",
        )
        _require(
            answer.get("condition") in {"transcript_only", "receipt_assisted"},
            f"{answer['case_id']}: bad answer condition",
        )
        _require(
            answer.get("expected_decision") in {"accept", "reject"},
            f"{answer['case_id']}: bad expected decision",
        )
        _require(
            isinstance(answer.get("scenario_id"), str)
            and isinstance(answer.get("category"), str),
            f"{answer['case_id']}: missing scenario metadata",
        )
        _require(
            isinstance(answer.get("expected_reason_codes"), list)
            and bool(answer["expected_reason_codes"])
            and set(answer["expected_reason_codes"]) <= set(allowed_reasons),
            f"{answer['case_id']}: bad expected reason codes",
        )
    _require(
        sum(answer["condition"] == "receipt_assisted" for answer in answers) == 6,
        "reviewer study v0 key must contain six cases per condition",
    )
    answer_by_id = {item.get("case_id"): item for item in answers if isinstance(item, dict)}
    _require(len(answer_by_id) == len(answers), "duplicate or invalid answer case id")
    response_by_id = {item.get("case_id"): item for item in responses if isinstance(item, dict)}
    _require(len(response_by_id) == len(responses), "duplicate or invalid response case id")
    _require(set(answer_by_id) == set(response_by_id), "response case ids do not match key")

    rows: list[dict[str, Any]] = []
    for case_id, answer in answer_by_id.items():
        supplied = response_by_id[case_id]
        decision = supplied.get("decision")
        reasons = supplied.get("reason_codes")
        probability = supplied.get("accept_probability")
        seconds = supplied.get("decision_seconds")
        _require(decision in {"accept", "reject"}, f"{case_id}: decision required")
        _require(
            isinstance(reasons, list)
            and bool(reasons)
            and all(isinstance(reason, str) for reason in reasons),
            f"{case_id}: at least one reason code required",
        )
        _require(
            set(reasons) <= set(allowed_reasons),
            f"{case_id}: response contains an unknown reason code",
        )
        _require(
            isinstance(probability, (int, float))
            and not isinstance(probability, bool)
            and 0 <= probability <= 1,
            f"{case_id}: accept_probability must be from 0 to 1",
        )
        _require(
            (decision == "accept" and probability >= 0.5)
            or (decision == "reject" and probability < 0.5),
            f"{case_id}: decision and accept_probability are inconsistent",
        )
        _require(
            isinstance(seconds, (int, float))
            and not isinstance(seconds, bool)
            and seconds > 0,
            f"{case_id}: decision_seconds must be positive",
        )
        expected = answer["expected_decision"]
        expected_reasons = set(answer["expected_reason_codes"])
        rows.append(
            {
                "participant_id": participant,
                "arm": arm,
                "case_id": case_id,
                "scenario_id": answer["scenario_id"],
                "category": answer["category"],
                "condition": answer["condition"],
                "correct": decision == expected,
                "unsafe_acceptance": expected == "reject" and decision == "accept",
                "sound_rejection": expected == "accept" and decision == "reject",
                "expected_unsafe": expected == "reject",
                "expected_sound": expected == "accept",
                "reason_detected": bool(expected_reasons.intersection(reasons)),
                "brier": (float(probability) - (1.0 if expected == "accept" else 0.0)) ** 2,
                "decision_seconds": float(seconds),
            }
        )
    return rows


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _decision_summary(selected: list[dict[str, Any]]) -> dict[str, Any]:
    unsafe = [row for row in selected if row["expected_unsafe"]]
    sound = [row for row in selected if row["expected_sound"]]
    return {
        "n_decisions": len(selected),
        "accuracy": _rate(sum(row["correct"] for row in selected), len(selected)),
        "unsafe_acceptance_rate": _rate(
            sum(row["unsafe_acceptance"] for row in unsafe), len(unsafe)
        ),
        "sound_rejection_rate": _rate(
            sum(row["sound_rejection"] for row in sound), len(sound)
        ),
        "reason_detection_rate": _rate(
            sum(row["reason_detected"] for row in selected), len(selected)
        ),
        "mean_brier_score": (
            round(sum(row["brier"] for row in selected) / len(selected), 4)
            if selected
            else None
        ),
        "mean_decision_seconds": (
            round(sum(row["decision_seconds"] for row in selected) / len(selected), 2)
            if selected
            else None
        ),
    }


def summarize(rows: list[dict[str, Any]], participants: int) -> dict[str, Any]:
    conditions: dict[str, dict[str, Any]] = {}
    for condition in ("transcript_only", "receipt_assisted"):
        selected = [row for row in rows if row["condition"] == condition]
        conditions[condition] = _decision_summary(selected)
    contrast: dict[str, float | None] = {}
    for metric in (
        "accuracy",
        "unsafe_acceptance_rate",
        "sound_rejection_rate",
        "reason_detection_rate",
        "mean_brier_score",
        "mean_decision_seconds",
    ):
        left = conditions["transcript_only"][metric]
        right = conditions["receipt_assisted"][metric]
        contrast[f"receipt_assisted_minus_transcript_only_{metric}"] = (
            round(right - left, 4) if left is not None and right is not None else None
        )
    arm_counts = {
        arm: len({row["participant_id"] for row in rows if row["arm"] == arm})
        for arm in ("A", "B")
    }
    per_scenario: dict[str, Any] = {}
    for scenario_id in sorted({row["scenario_id"] for row in rows}):
        scenario_rows = [row for row in rows if row["scenario_id"] == scenario_id]
        per_scenario[scenario_id] = {
            "category": scenario_rows[0]["category"],
            "conditions": {
                condition: _decision_summary(
                    [row for row in scenario_rows if row["condition"] == condition]
                )
                for condition in ("transcript_only", "receipt_assisted")
            },
        }
    per_category = {
        category: {
            condition: _decision_summary(
                [
                    row
                    for row in rows
                    if row["category"] == category and row["condition"] == condition
                ]
            )
            for condition in ("transcript_only", "receipt_assisted")
        }
        for category in sorted({row["category"] for row in rows})
    }
    warnings = []
    if arm_counts["A"] != arm_counts["B"]:
        warnings.append("arms_are_not_balanced")
    return {
        "study_version": "evidencegate_reviewer_study_v0",
        "participants": participants,
        "arm_counts": arm_counts,
        "design_warnings": warnings,
        "conditions": conditions,
        "descriptive_contrast": contrast,
        "per_category": per_category,
        "per_scenario": per_scenario,
        "inference": {
            "status": "not_estimated",
            "reason": (
                "This standard-library scorer reports descriptive outcomes only. "
                "Apply the pre-registered analysis to a completed, adequately powered "
                "cohort before making effect claims."
            ),
        },
    }


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pair",
        nargs=2,
        action="append",
        metavar=("COORDINATOR_KEY", "RESPONSE"),
        required=True,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        rows: list[dict[str, Any]] = []
        participants: set[str] = set()
        for key_name, response_name in args.pair:
            key = _load(Path(key_name))
            response = _load(Path(response_name))
            participant = key.get("participant_id")
            _require(participant not in participants, f"duplicate participant: {participant}")
            participants.add(participant)
            rows.extend(score_pair(key, response))
        result = summarize(rows, len(participants))
        rendered = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except (OSError, TypeError, ValueError, ScoringError) as exc:
        print(f"FAIL reviewer study scoring: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
