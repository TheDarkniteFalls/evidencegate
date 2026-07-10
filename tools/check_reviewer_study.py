#!/usr/bin/env python3
"""Check reviewer-study blinding, counterbalancing, and scoring contracts."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from prepare_reviewer_study import build_materials, load_scenarios  # noqa: E402
from score_reviewer_study import score_pair, summarize  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    try:
        study = load_scenarios()
        packet_a, response_a, key_a = build_materials(
            study,
            participant="synthetic-format-check-a",
            arm="A",
            seed="study-contract-self-test",
        )
        _, response_b, key_b = build_materials(
            study,
            participant="synthetic-format-check-b",
            arm="B",
            seed="study-contract-self-test",
        )
        condition_a = {item["scenario_id"]: item["condition"] for item in key_a["answers"]}
        condition_b = {item["scenario_id"]: item["condition"] for item in key_b["answers"]}
        require(
            all(condition_a[name] != condition_b[name] for name in condition_a),
            "arms are not complementary",
        )
        require(
            list(condition_a.values()).count("receipt_assisted") == len(condition_a) // 2,
            "arm is not balanced",
        )
        serialized_packet = repr(packet_a)
        for forbidden in ("ground_truth", "scenario_id", "expected_decision", "category"):
            require(forbidden not in serialized_packet, f"participant packet leaks {forbidden}")

        for key, response_set in ((key_a, response_a), (key_b, response_b)):
            answer_by_id = {item["case_id"]: item for item in key["answers"]}
            for response in response_set["responses"]:
                answer = answer_by_id[response["case_id"]]
                response["decision"] = answer["expected_decision"]
                response["reason_codes"] = answer["expected_reason_codes"]
                response["accept_probability"] = (
                    0.9 if answer["expected_decision"] == "accept" else 0.1
                )
                response["decision_seconds"] = 10
        rows = score_pair(key_a, response_a) + score_pair(key_b, response_b)
        summary = summarize(rows, 2)
        require(len(rows) == len(condition_a) * 2, "scorer lost decisions")
        require(
            summary["conditions"]["transcript_only"]["accuracy"] == 1.0
            and summary["conditions"]["receipt_assisted"]["accuracy"] == 1.0,
            "scorer contract is inconsistent",
        )
        require(summary["arm_counts"] == {"A": 1, "B": 1}, "arm counts are wrong")
        require(not summary["design_warnings"], "balanced self-test has warnings")
        require(
            all(
                values["conditions"]["transcript_only"]["n_decisions"] == 1
                and values["conditions"]["receipt_assisted"]["n_decisions"] == 1
                for values in summary["per_scenario"].values()
            ),
            "per-scenario counterbalancing is not visible",
        )
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"FAIL reviewer_study_v0: {exc}")
        return 1
    print("PASS reviewer study blinded packet contract")
    print("PASS reviewer study complementary arm contract")
    print("PASS reviewer study scorer format contract (synthetic self-test only)")
    print("PASS reviewer_study_v0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
