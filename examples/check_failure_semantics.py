#!/usr/bin/env python3
"""Validate and summarize the synthetic failure-semantics fixture."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


FIXTURE = Path(__file__).with_name("failure-semantics.json")
EXECUTION_STATUSES = {"completed", "failed"}
SCORING_STATUSES = {"scored", "refused", "failed", "not_scored", "abstained"}


def load_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_fixture(fixture: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if fixture.get("schema_version") != "evidencegate_failure_semantics_v0":
        errors.append("schema_version must be evidencegate_failure_semantics_v0")

    scale = fixture.get("score_scale")
    if not isinstance(scale, dict):
        errors.append("score_scale must be an object")
        minimum = maximum = None
    else:
        minimum = scale.get("minimum")
        maximum = scale.get("maximum")
        if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
            errors.append("score_scale.minimum must be numeric")
        if not isinstance(maximum, (int, float)) or isinstance(maximum, bool):
            errors.append("score_scale.maximum must be numeric")
        if (
            isinstance(minimum, (int, float))
            and not isinstance(minimum, bool)
            and isinstance(maximum, (int, float))
            and not isinstance(maximum, bool)
            and minimum >= maximum
        ):
            errors.append("score_scale.minimum must be less than maximum")
        if scale.get("higher_is_more_concerning") is not True:
            errors.append("score_scale.higher_is_more_concerning must be true")

    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty list"]

    seen_ids: set[str] = set()
    for index, case in enumerate(cases, start=1):
        location = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{location} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{location}.id must be non-empty text")
        elif case_id in seen_ids:
            errors.append(f"duplicate case id: {case_id}")
        else:
            seen_ids.add(case_id)
        if not isinstance(case.get("description"), str) or not case["description"]:
            errors.append(f"{location}.description must be non-empty text")

        execution_status = case.get("execution_status")
        scoring_status = case.get("scoring_status")
        score = case.get("score")
        failure_class = case.get("failure_class")
        evidence_status = case.get("evidence_status")

        if execution_status not in EXECUTION_STATUSES:
            errors.append(f"{location}.execution_status is unsupported")
        if scoring_status not in SCORING_STATUSES:
            errors.append(f"{location}.scoring_status is unsupported")
        if execution_status == "failed" and scoring_status == "scored":
            errors.append(f"{location}: failed execution must not be scored")
        if execution_status == "failed" and scoring_status != "not_scored":
            errors.append(
                f"{location}: failed execution must use not_scored status"
            )

        if scoring_status == "scored":
            if not isinstance(score, (int, float)) or isinstance(score, bool):
                errors.append(f"{location}.score must be numeric when scored")
            elif (
                isinstance(minimum, (int, float))
                and isinstance(maximum, (int, float))
                and not minimum <= score <= maximum
            ):
                errors.append(f"{location}.score is outside the declared scale")
            if failure_class is not None:
                errors.append(f"{location}.failure_class must be null when scored")
            if evidence_status != "available":
                errors.append(
                    f"{location}.evidence_status must be available when scored"
                )
        else:
            if score is not None:
                errors.append(f"{location}.score must be null when not scored")
            if not isinstance(failure_class, str) or not failure_class:
                errors.append(
                    f"{location}.failure_class is required when not scored"
                )
            if evidence_status != "missing":
                errors.append(
                    f"{location}.evidence_status must be missing when not scored"
                )
    return errors


def summarize_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    errors = validate_fixture(fixture)
    if errors:
        raise ValueError("; ".join(errors))

    cases = fixture["cases"]
    scale = fixture["score_scale"]
    scored = [case for case in cases if case["scoring_status"] == "scored"]
    missing_count = len(cases) - len(scored)
    score_total = sum(case["score"] for case in scored)
    counts = Counter(case["scoring_status"] for case in cases)
    failure_classes = Counter(
        case["failure_class"]
        for case in cases
        if case["evidence_status"] == "missing"
    )
    attempted_count = len(cases)
    return {
        "attempted_count": attempted_count,
        "scored_count": len(scored),
        "execution_failed_count": sum(
            case["execution_status"] == "failed" for case in cases
        ),
        "scoring_status_counts": {
            status: counts.get(status, 0) for status in sorted(SCORING_STATUSES)
        },
        "missing_failure_class_counts": dict(sorted(failure_classes.items())),
        "scoring_coverage": len(scored) / attempted_count,
        "observed_mean": score_total / len(scored) if scored else None,
        "best_case_mean": (
            score_total + missing_count * scale["minimum"]
        ) / attempted_count,
        "worst_case_mean": (
            score_total + missing_count * scale["maximum"]
        ) / attempted_count,
    }


def main() -> int:
    fixture = load_fixture()
    errors = validate_fixture(fixture)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1

    summary = summarize_fixture(fixture)
    scored = summary["scored_count"]
    attempted = summary["attempted_count"]
    print("PASS case_schema")
    print("PASS missing_is_not_safe")
    print("PASS failed_target_not_scored")
    print(
        f"PASS scoring_coverage {scored}/{attempted} "
        f"({summary['scoring_coverage']:.1%})"
    )
    counts = summary["scoring_status_counts"]
    print(
        "PASS scoring_status_counts "
        + " ".join(f"{status}={count}" for status, count in counts.items())
    )
    failure_classes = summary["missing_failure_class_counts"]
    print(
        "PASS missing_failure_classes "
        + " ".join(
            f"{failure_class}={count}"
            for failure_class, count in failure_classes.items()
        )
    )
    observed_mean = summary["observed_mean"]
    if observed_mean is None:
        print("PASS observed_mean unavailable")
    else:
        print(f"PASS observed_mean {observed_mean:.2f}")
    print(
        "PASS concern_bounds "
        f"{summary['best_case_mean']:.2f}..{summary['worst_case_mean']:.2f}"
    )
    print("PASS failure_semantics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
