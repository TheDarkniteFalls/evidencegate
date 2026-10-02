#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline structural and semantic validator for the experimental v0 profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


CONTRACT = "evalbraid_evaluation_provenance_result_v0"
PROFILE = "evalbraid_evaluation_provenance_v0"
MAX_RECORD_BYTES = 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "evalbraid-evaluation-provenance-v0.schema.json"
CORE_LAYERS = {
    "trajectory_agent_self_check",
    "verifier_definition",
    "executed_verifier",
    "handoff_lifecycle",
}


class DuplicateKeyError(ValueError):
    """Raised when strict JSON loading sees a repeated object key."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _contains_unpaired_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        index = 0
        while index < len(value):
            code = ord(value[index])
            if 0xD800 <= code <= 0xDBFF:
                if index + 1 >= len(value) or not 0xDC00 <= ord(value[index + 1]) <= 0xDFFF:
                    return True
                index += 2
                continue
            if 0xDC00 <= code <= 0xDFFF:
                return True
            index += 1
        return False
    if isinstance(value, dict):
        return any(
            _contains_unpaired_surrogate(key) or _contains_unpaired_surrogate(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_unpaired_surrogate(child) for child in value)
    return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _pointer(parts: Iterable[Any]) -> str:
    tokens = [_escape(str(part)) for part in parts]
    return "" if not tokens else "/" + "/".join(tokens)


def _finding(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _sort_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = {(item["code"], item["path"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["path"], item["code"], item["message"]))


def _result(
    *, record_sha256: str | None, schema_sha256: str, findings: list[dict[str, str]]
) -> dict[str, Any]:
    ordered = _sort_findings(findings)
    return {
        "contract": CONTRACT,
        "valid": not ordered,
        "profile": PROFILE,
        "record_sha256": record_sha256,
        "schema_sha256": schema_sha256,
        "findings": ordered,
    }


def _load_schema(schema_path: Path) -> tuple[dict[str, Any], str, FormatChecker]:
    schema_bytes = schema_path.read_bytes()
    schema_sha256 = _sha256(schema_bytes)
    schema = json.loads(schema_bytes.decode("utf-8"), object_pairs_hook=_strict_object)
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()
    missing = sorted({"uuid", "date-time", "uri"} - set(checker.checkers))
    if missing:
        raise RuntimeError("missing format checker(s): " + ", ".join(missing))
    return schema, schema_sha256, checker


def _observed_value(field: Any) -> Any | None:
    if isinstance(field, dict) and field.get("status") == "observed":
        return field.get("value")
    return None


def _expected_layer(path: str) -> str | None:
    if path.startswith("/trajectory/"):
        return "trajectory_agent_self_check"
    if path.startswith("/agent_handoff/"):
        return "handoff_lifecycle"
    if path.startswith("/verifier_definition/policy_references"):
        return "policy"
    if path.startswith("/verifier_definition/"):
        return "verifier_definition"
    if path.startswith("/verifier_start/") or path.startswith("/verifier_result/"):
        return "executed_verifier"
    if path.startswith("/measurements/"):
        return "executed_verifier"
    if path.startswith("/evaluation_judgment/integrity_basis/policy_references"):
        return "policy"
    if path.startswith("/adjudication/"):
        return "adjudication"
    return None


def _reference_uses(record: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    uses: list[tuple[str, str, str | None]] = []

    def walk(value: Any, parts: list[Any]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_parts = [*parts, key]
                child_path = _pointer(child_parts)
                if key in {"evidence_references", "basis_references", "policy_references"}:
                    if isinstance(child, list):
                        expected = _expected_layer(child_path)
                        for index, reference_id in enumerate(child):
                            if isinstance(reference_id, str):
                                uses.append((reference_id, _pointer([*child_parts, index]), expected))
                else:
                    walk(child, child_parts)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, [*parts, index])

    for key, value in record.items():
        if key != "source_references":
            walk(value, [key])
    return uses


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def _resolve_pointer(record: Any, path: str) -> tuple[bool, Any]:
    if not path.startswith("/"):
        return False, None
    current = record
    for raw_segment in path[1:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if segment not in current:
                return False, None
            current = current[segment]
        elif isinstance(current, list):
            if not segment.isdigit() or (len(segment) > 1 and segment.startswith("0")):
                return False, None
            index = int(segment)
            if index >= len(current):
                return False, None
            current = current[index]
        else:
            return False, None
    return True, current


def _semantic_findings(record: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    sources = record["source_references"]
    source_ids = [source["reference_id"] for source in sources]
    counts = Counter(source_ids)
    first_source: dict[str, dict[str, Any]] = {}
    first_index: dict[str, int] = {}
    for index, source in enumerate(sources):
        first_source.setdefault(source["reference_id"], source)
        first_index.setdefault(source["reference_id"], index)

    for index, source in enumerate(sources):
        reference_id = source["reference_id"]
        if counts[reference_id] > 1 and first_index[reference_id] != index:
            findings.append(
                _finding(
                    "profile_reference_duplicate",
                    f"/source_references/{index}/reference_id",
                    "reference_id duplicates an earlier source reference",
                )
            )

    uses = _reference_uses(record)
    used_ids: set[str] = set()
    for reference_id, path, expected_layer in uses:
        source = first_source.get(reference_id)
        if source is None:
            findings.append(
                _finding(
                    "profile_reference_unresolved",
                    path,
                    "reference id does not resolve within source_references",
                )
            )
            continue
        used_ids.add(reference_id)
        if expected_layer is not None and source["layer"] != expected_layer:
            findings.append(
                _finding(
                    "profile_reference_layer_invalid",
                    path,
                    f"section requires a {expected_layer} source reference",
                )
            )

    for index, source in enumerate(sources):
        if source["reference_id"] not in used_ids:
            findings.append(
                _finding(
                    "profile_reference_orphaned",
                    f"/source_references/{index}/reference_id",
                    "source reference is not used by a semantic section",
                )
            )

    present_layers = {source["layer"] for source in sources}
    for layer in sorted(CORE_LAYERS - present_layers):
        findings.append(
            _finding(
                "profile_layer_missing",
                "/source_references",
                f"required core evidence layer is missing: {layer}",
            )
        )

    for index, source in enumerate(sources):
        availability = source["availability"]
        digest_status = source["digest"]["status"]
        if availability == "available" and digest_status != "observed":
            findings.append(
                _finding(
                    "profile_source_availability_invalid",
                    f"/source_references/{index}/availability",
                    "available evidence requires an observed digest",
                )
            )
        elif availability == "not_observed" and digest_status == "observed":
            findings.append(
                _finding(
                    "profile_source_availability_invalid",
                    f"/source_references/{index}/availability",
                    "not_observed evidence cannot present an observed digest",
                )
            )

    identity_digest = _observed_value(record["identity"]["verifier_digest"])
    definition_digest = _observed_value(record["verifier_definition"]["verifier_digest"])
    if identity_digest is not None and definition_digest is not None and identity_digest != definition_digest:
        findings.append(
            _finding(
                "profile_verifier_digest_mismatch",
                "/verifier_definition/verifier_digest/value",
                "verifier definition digest differs from the identity digest",
            )
        )

    handoff = record["agent_handoff"]
    artifact_ids = {item["artifact_id"] for item in handoff["relevant_artifacts"]}
    process_ids = {item["process_id"] for item in handoff["relevant_processes"]}
    for index, observation in enumerate(record["verifier_start"]["liveness_observations"]):
        known_ids = artifact_ids if observation["subject_kind"] == "artifact" else process_ids
        if observation["subject_id"] not in known_ids:
            findings.append(
                _finding(
                    "profile_handoff_link_mismatch",
                    f"/verifier_start/liveness_observations/{index}/subject_id",
                    "verifier-start subject does not match a same-kind handoff subject",
                )
            )

    exit_value = _observed_value(handoff["agent_exit_time"])
    start_value = _observed_value(record["verifier_start"]["timestamp"])
    adjudication = record["adjudication"]
    adjudication_value = _observed_value(adjudication["timestamp"])
    exit_time = _parse_timestamp(exit_value) if isinstance(exit_value, str) else None
    start_time = _parse_timestamp(start_value) if isinstance(start_value, str) else None
    adjudication_time = _parse_timestamp(adjudication_value) if isinstance(adjudication_value, str) else None
    if exit_time is not None and start_time is not None and exit_time > start_time:
        findings.append(
            _finding(
                "profile_time_order_invalid",
                "/verifier_start/timestamp/value",
                "observed verifier start precedes observed agent exit",
            )
        )
    if adjudication["status"] == "resolved" and adjudication_time is not None:
        evidence_times = [value for value in (exit_time, start_time) if value is not None]
        if evidence_times and adjudication_time < max(evidence_times):
            findings.append(
                _finding(
                    "profile_time_order_invalid",
                    "/adjudication/timestamp/value",
                    "resolved adjudication precedes observed evidence timing",
                )
            )

    judgment = record["evaluation_judgment"]
    judgment_uses_self_check = any(
        path.startswith("/evaluation_judgment/")
        and reference_id in first_source
        and first_source[reference_id]["layer"] == "trajectory_agent_self_check"
        for reference_id, path, _expected_layer in uses
    )
    if judgment["evidence_independence"] == "independent" and judgment_uses_self_check:
        findings.append(
            _finding(
                "profile_judgment_independence_invalid",
                "/evaluation_judgment/evidence_independence",
                "independent judgment cannot rely on trajectory_agent_self_check evidence",
            )
        )
    expected_triggers: set[str] = set()
    trigger_fields = (
        (judgment["reward_alignment"] == "possible_mismatch", "possible_mismatch"),
        (judgment["reward_alignment"] == "confirmed_mismatch", "confirmed_mismatch"),
        (judgment["integrity_signal"] == "ambiguous", "ambiguous_integrity_signal"),
        (judgment["integrity_signal"] == "possible_shortcut", "possible_shortcut"),
        (judgment["integrity_signal"] == "confirmed_shortcut", "confirmed_shortcut"),
        (judgment["confidence"] == "low", "low_confidence_core_judgment"),
        (judgment["claim_severity"] == "high", "high_severity_claim"),
    )
    for condition, trigger in trigger_fields:
        if condition:
            expected_triggers.add(trigger)
    if set(adjudication["triggers"]) != expected_triggers:
        findings.append(
            _finding(
                "profile_trigger_set_invalid",
                "/adjudication/triggers",
                "adjudication triggers do not equal the frozen judgment-derived set",
            )
        )
    if adjudication["triggered"] != bool(expected_triggers):
        findings.append(
            _finding(
                "profile_trigger_set_invalid",
                "/adjudication/triggered",
                "adjudication triggered flag does not match the frozen trigger set",
            )
        )

    pointer_validity: dict[str, tuple[bool, Any]] = {}
    for collection in ("retained_fields", "revised_fields"):
        entries = adjudication[collection]
        for index, entry in enumerate(entries):
            path = entry if collection == "retained_fields" else entry["path"]
            resolved, value = _resolve_pointer(record, path)
            allowed = path.startswith("/evaluation_judgment/")
            pointer_validity[path] = (resolved and allowed, value)
            if not resolved or not allowed:
                suffix = "" if collection == "retained_fields" else "/path"
                findings.append(
                    _finding(
                        "profile_adjudication_pointer_invalid",
                        f"/adjudication/{collection}/{index}{suffix}",
                        "path must resolve to a field below evaluation_judgment",
                    )
                )

    for index, revision in enumerate(adjudication["revised_fields"]):
        path = revision["path"]
        valid_pointer, final_value = pointer_validity.get(path, (False, None))
        if not valid_pointer:
            continue
        if revision["prior_value"] == revision["revised_value"] or final_value != revision["revised_value"]:
            findings.append(
                _finding(
                    "profile_revision_value_invalid",
                    f"/adjudication/revised_fields/{index}",
                    "revision must change the prior value and equal the final record value",
                )
            )

    for index, fact in enumerate(judgment["proven_facts"]):
        references = fact["evidence_references"]
        if not any(
            reference_id in first_source and first_source[reference_id]["availability"] == "available"
            for reference_id in references
        ):
            findings.append(
                _finding(
                    "profile_proven_fact_evidence_invalid",
                    f"/evaluation_judgment/proven_facts/{index}/evidence_references",
                    "proven fact requires at least one resolved, available source reference",
                )
            )

    source_rank = {"internal_only": 0, "reference_only": 1, "cleared": 2}
    record_rank = {"internal_only": 0, "review_required": 1, "cleared": 2}
    allowed_rank = min((source_rank[source["redistribution"]] for source in sources), default=2)
    handling = record["data_handling"]
    if handling["classification"] in {"internal", "confidential"} or any(
        handling[field]
        for field in (
            "contains_personal_data",
            "contains_secrets",
            "contains_raw_trajectory",
            "contains_task_assets",
        )
    ):
        allowed_rank = min(allowed_rank, 0)
    if record_rank[handling["redistribution_status"]] > allowed_rank:
        findings.append(
            _finding(
                "profile_redistribution_invalid",
                "/data_handling/redistribution_status",
                "record redistribution exceeds a cited source or content restriction",
            )
        )

    for index, check in enumerate(record["trajectory"]["self_checks"]):
        if check["independence"] != "self_authored":
            findings.append(
                _finding(
                    "profile_self_check_independence_invalid",
                    f"/trajectory/self_checks/{index}/independence",
                    "agent self-checks must remain self_authored",
                )
            )

    return _sort_findings(findings)


def validate_path(
    record_path: Path, schema_path: Path = DEFAULT_SCHEMA
) -> tuple[str, int, dict[str, Any]]:
    """Return (stage, exit code, stable result) without mutating any input."""

    try:
        schema, schema_sha256, checker = _load_schema(schema_path)
    except RuntimeError as exc:
        result = _result(
            record_sha256=None,
            schema_sha256=_sha256(schema_path.read_bytes()) if schema_path.is_file() else "",
            findings=[_finding("profile_format_checker_unavailable", "", str(exc))],
        )
        return "tool_error", 2, result
    except Exception as exc:  # validator bootstrap failures are tool errors
        result = _result(
            record_sha256=None,
            schema_sha256="",
            findings=[_finding("profile_tool_error", "", f"schema initialization failed: {exc}")],
        )
        return "tool_error", 2, result

    try:
        size = record_path.stat().st_size
    except OSError as exc:
        result = _result(
            record_sha256=None,
            schema_sha256=schema_sha256,
            findings=[_finding("profile_tool_error", "", f"record stat failed: {exc}")],
        )
        return "tool_error", 2, result
    if size > MAX_RECORD_BYTES:
        result = _result(
            record_sha256=None,
            schema_sha256=schema_sha256,
            findings=[
                _finding(
                    "profile_load_too_large",
                    "",
                    f"record exceeds the {MAX_RECORD_BYTES}-byte limit",
                )
            ],
        )
        return "load_error", 2, result

    try:
        record_bytes = record_path.read_bytes()
    except OSError as exc:
        result = _result(
            record_sha256=None,
            schema_sha256=schema_sha256,
            findings=[_finding("profile_tool_error", "", f"record read failed: {exc}")],
        )
        return "tool_error", 2, result
    record_sha256 = _sha256(record_bytes)
    if len(record_bytes) > MAX_RECORD_BYTES:
        result = _result(
            record_sha256=None,
            schema_sha256=schema_sha256,
            findings=[_finding("profile_load_too_large", "", "record changed beyond the byte limit while reading")],
        )
        return "load_error", 2, result

    try:
        text = record_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        result = _result(
            record_sha256=record_sha256,
            schema_sha256=schema_sha256,
            findings=[_finding("profile_load_utf8_invalid", "", f"record is not UTF-8: {exc}")],
        )
        return "load_error", 2, result
    try:
        record = json.loads(text, object_pairs_hook=_strict_object)
    except DuplicateKeyError as exc:
        result = _result(
            record_sha256=record_sha256,
            schema_sha256=schema_sha256,
            findings=[_finding("profile_load_duplicate_key", "", f"duplicate object key: {exc.key}")],
        )
        return "load_error", 2, result
    except json.JSONDecodeError as exc:
        result = _result(
            record_sha256=record_sha256,
            schema_sha256=schema_sha256,
            findings=[_finding("profile_load_json_invalid", "", f"invalid JSON at line {exc.lineno}, column {exc.colno}")],
        )
        return "load_error", 2, result
    if _contains_unpaired_surrogate(record):
        result = _result(
            record_sha256=record_sha256,
            schema_sha256=schema_sha256,
            findings=[
                _finding(
                    "profile_load_invalid_unicode",
                    "",
                    "unpaired Unicode surrogate is not allowed",
                )
            ],
        )
        return "load_error", 2, result

    try:
        validator = Draft202012Validator(schema, format_checker=checker)
        schema_findings = [
            _finding("profile_schema_invalid", _pointer(error.absolute_path), error.message)
            for error in validator.iter_errors(record)
        ]
    except Exception as exc:
        result = _result(
            record_sha256=record_sha256,
            schema_sha256=schema_sha256,
            findings=[_finding("profile_tool_error", "", f"structural validation failed: {exc}")],
        )
        return "tool_error", 2, result
    if schema_findings:
        return "schema_error", 1, _result(
            record_sha256=record_sha256,
            schema_sha256=schema_sha256,
            findings=schema_findings,
        )

    semantic_findings = _semantic_findings(record)
    if semantic_findings:
        return "semantic_error", 1, _result(
            record_sha256=record_sha256,
            schema_sha256=schema_sha256,
            findings=semantic_findings,
        )
    return "pass", 0, _result(
        record_sha256=record_sha256,
        schema_sha256=schema_sha256,
        findings=[],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    stage, exit_code, result = validate_path(args.record)
    if args.as_json:
        print(json.dumps(result, sort_keys=False, separators=(",", ":")))
    else:
        print(f"{stage}: {'valid' if result['valid'] else 'invalid'}")
        for finding in result["findings"]:
            print(f"{finding['code']} {finding['path']}: {finding['message']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
