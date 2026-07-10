#!/usr/bin/env python3
"""Validate, verify, and render receipts for human-reviewed agent work."""

from __future__ import annotations

import argparse
import copy
import html
import json
import math
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


LEGACY_PASS_STATUSES = {"passed", "skipped"}
V1_CHECK_STATUSES = {"passed", "failed", "skipped", "unknown"}
V1_HUMAN_REVIEW_STATUSES = {"approved", "changes_requested", "pending"}
V1_PUBLIC_SAFETY_STATUSES = {"reviewed", "pending", "not_applicable"}
SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
BOUNDARY = (
    "This receipt records supplied evidence. It does not prove that commands ran, "
    "that evidence or reviewer identities are authentic, or that the work is correct, "
    "secure, accepted, or authorized for publication."
)
MAX_PACKET_BYTES = 1_000_000
GIT_TIMEOUT_SECONDS = 30
V1_TOP_LEVEL_FIELDS = {
    "schema_version",
    "summary",
    "subject",
    "scope",
    "files_touched",
    "checks",
    "claims",
    "risks",
    "human_review",
    "public_safety",
    "extensions",
}
V1_SUBJECT_FIELDS = {"type", "base_sha", "head_sha"}
V1_SCOPE_FIELDS = {"allowed_paths", "protected_prefixes"}
V1_CHECK_FIELDS = {
    "id",
    "name",
    "command",
    "status",
    "summary",
    "scope",
    "revision",
    "required",
}
V1_CLAIM_FIELDS = {"id", "text", "evidence_refs"}
V1_HUMAN_REVIEW_FIELDS = {
    "status",
    "reviewer",
    "reviewed_head_sha",
    "summary",
}
V1_PUBLIC_SAFETY_FIELDS = {"status", "reviewed_head_sha", "summary"}
MARKDOWN_ESCAPE_PATTERN = re.compile(r"([\\`*_{}\[\]()#!|>])")


def require_text(packet: dict[str, Any], key: str, errors: list[str]) -> None:
    if not isinstance(packet.get(key), str) or not packet[key].strip():
        errors.append(f"{key} must be non-empty text")


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_text_field(
    value: dict[str, Any], key: str, location: str, errors: list[str]
) -> None:
    if not _is_text(value.get(key)):
        errors.append(f"{location}.{key} must be non-empty text")


def _require_sha(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or SHA_PATTERN.fullmatch(value) is None:
        errors.append(f"{location} must be a full 40-character Git commit SHA")


def _require_id(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        errors.append(
            f"{location} must start with a letter or number and use only letters, "
            "numbers, '.', '_', ':', or '-'"
        )


def _valid_repo_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if value.startswith("/") or "\\" in value or "//" in value:
        return False
    if any(ord(character) < 32 for character in value):
        return False
    parsed = PurePosixPath(value)
    if parsed.as_posix() != value:
        return False
    parts = parsed.parts
    return bool(parts) and parts != (".",) and all(part not in {"", ".", ".."} for part in parts)


def _require_path_list(value: Any, location: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{location} must be a list of relative Git paths")
        return []
    paths: list[str] = []
    for index, item in enumerate(value, start=1):
        if not _valid_repo_path(item):
            errors.append(f"{location}[{index}] must be a safe relative Git path")
            continue
        paths.append(item)
    if len(paths) != len(set(paths)):
        errors.append(f"{location} must not contain duplicate paths")
    return paths


def _require_text_list(
    value: Any, location: str, errors: list[str], *, nonempty: bool = True
) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        suffix = "a non-empty list of text" if nonempty else "a list of text"
        errors.append(f"{location} must be {suffix}")
        return []
    items: list[str] = []
    for index, item in enumerate(value, start=1):
        if not _is_text(item):
            errors.append(f"{location}[{index}] must be non-empty text")
            continue
        items.append(item)
    return items


def _reject_unknown_fields(
    value: dict[str, Any], allowed: set[str], location: str, errors: list[str]
) -> None:
    for key in sorted(set(value) - allowed):
        field = f"{location}.{key}" if location else key
        errors.append(
            f"{field} is not defined by EvidenceGate v1; "
            "put non-authoritative metadata under extensions"
        )


def _is_protected(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def receipt_version(packet: dict[str, Any]) -> str:
    if "schema_version" not in packet:
        return "legacy"
    if type(packet.get("schema_version")) is int and packet["schema_version"] == 1:
        return "v1"
    return "unsupported"


def validate_legacy_packet(packet: dict[str, Any]) -> list[str]:
    """Validate the original structural-only receipt format."""
    errors: list[str] = []
    require_text(packet, "summary", errors)

    commands = packet.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty list")
    else:
        for index, command in enumerate(commands, start=1):
            if (
                not isinstance(command, dict)
                or not command.get("command")
                or command.get("result") not in LEGACY_PASS_STATUSES
            ):
                errors.append(
                    f"commands[{index}] needs command plus result passed/skipped"
                )

    files = packet.get("files_touched")
    if not isinstance(files, list) or not all(
        isinstance(item, str) and item for item in files
    ):
        errors.append("files_touched must be a list of paths")

    tests = packet.get("tests")
    if not isinstance(tests, list) or not tests:
        errors.append("tests must be a non-empty list")
    else:
        for index, test in enumerate(tests, start=1):
            if (
                not isinstance(test, dict)
                or not test.get("name")
                or test.get("status") != "passed"
            ):
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


def validate_v1_packet(packet: dict[str, Any]) -> list[str]:
    """Validate the v1 schema and its internal evidence relationships."""
    errors: list[str] = []
    _reject_unknown_fields(packet, V1_TOP_LEVEL_FIELDS, "", errors)
    if type(packet.get("schema_version")) is not int or packet.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    require_text(packet, "summary", errors)

    subject = packet.get("subject")
    head_sha: str | None = None
    if not isinstance(subject, dict):
        errors.append("subject must be an object")
    else:
        _reject_unknown_fields(subject, V1_SUBJECT_FIELDS, "subject", errors)
        if subject.get("type") != "git_change":
            errors.append("subject.type must be git_change")
        _require_sha(subject.get("base_sha"), "subject.base_sha", errors)
        _require_sha(subject.get("head_sha"), "subject.head_sha", errors)
        if isinstance(subject.get("head_sha"), str):
            head_sha = subject["head_sha"].lower()
        if (
            isinstance(subject.get("base_sha"), str)
            and isinstance(subject.get("head_sha"), str)
            and subject["base_sha"].lower() == subject["head_sha"].lower()
        ):
            errors.append("subject.base_sha and subject.head_sha must differ")

    files_touched = _require_path_list(
        packet.get("files_touched"), "files_touched", errors
    )
    if not files_touched:
        errors.append("files_touched must contain at least one path")

    scope = packet.get("scope")
    allowed_paths: list[str] = []
    protected_prefixes: list[str] = []
    if not isinstance(scope, dict):
        errors.append("scope must be an object")
    else:
        _reject_unknown_fields(scope, V1_SCOPE_FIELDS, "scope", errors)
        allowed_paths = _require_path_list(
            scope.get("allowed_paths"), "scope.allowed_paths", errors
        )
        protected_prefixes = _require_path_list(
            scope.get("protected_prefixes"), "scope.protected_prefixes", errors
        )
        if not allowed_paths:
            errors.append("scope.allowed_paths must contain at least one path")

    if files_touched and allowed_paths:
        outside_scope = sorted(set(files_touched) - set(allowed_paths))
        if outside_scope:
            errors.append(
                "files_touched outside scope.allowed_paths: "
                + ", ".join(outside_scope)
            )
    if files_touched and protected_prefixes:
        protected = sorted(
            path for path in files_touched if _is_protected(path, protected_prefixes)
        )
        if protected:
            errors.append("files_touched include protected paths: " + ", ".join(protected))

    checks = packet.get("checks")
    check_by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty list")
    else:
        for index, check in enumerate(checks, start=1):
            location = f"checks[{index}]"
            if not isinstance(check, dict):
                errors.append(f"{location} must be an object")
                continue
            _reject_unknown_fields(check, V1_CHECK_FIELDS, location, errors)
            check_id = check.get("id")
            _require_id(check_id, f"{location}.id", errors)
            _require_text_field(check, "name", location, errors)
            _require_text_field(check, "command", location, errors)
            _require_text_field(check, "summary", location, errors)
            _require_text_field(check, "scope", location, errors)
            _require_sha(check.get("revision"), f"{location}.revision", errors)
            if check.get("status") not in V1_CHECK_STATUSES:
                errors.append(
                    f"{location}.status must be one of: "
                    + ", ".join(sorted(V1_CHECK_STATUSES))
                )
            if not isinstance(check.get("required"), bool):
                errors.append(f"{location}.required must be true or false")
            if isinstance(check_id, str) and ID_PATTERN.fullmatch(check_id):
                if check_id in check_by_id:
                    errors.append(f"duplicate check id: {check_id}")
                else:
                    check_by_id[check_id] = check
            revision = check.get("revision")
            if head_sha is not None and isinstance(revision, str):
                if SHA_PATTERN.fullmatch(revision) and revision.lower() != head_sha:
                    errors.append(
                        f"{location}.revision does not match subject.head_sha"
                    )

    claims = packet.get("claims")
    seen_claim_ids: set[str] = set()
    if not isinstance(claims, list) or not claims:
        errors.append("claims must be a non-empty list")
    else:
        for index, claim in enumerate(claims, start=1):
            location = f"claims[{index}]"
            if not isinstance(claim, dict):
                errors.append(f"{location} must be an object")
                continue
            _reject_unknown_fields(claim, V1_CLAIM_FIELDS, location, errors)
            claim_id = claim.get("id")
            _require_id(claim_id, f"{location}.id", errors)
            _require_text_field(claim, "text", location, errors)
            if isinstance(claim_id, str) and ID_PATTERN.fullmatch(claim_id):
                if claim_id in seen_claim_ids:
                    errors.append(f"duplicate claim id: {claim_id}")
                seen_claim_ids.add(claim_id)
            refs = claim.get("evidence_refs")
            if not isinstance(refs, list) or not refs:
                errors.append(f"{location}.evidence_refs must be a non-empty list")
                continue
            if not all(isinstance(ref, str) and ref for ref in refs):
                errors.append(f"{location}.evidence_refs must contain check IDs")
                continue
            if len(refs) != len(set(refs)):
                errors.append(f"{location}.evidence_refs must not contain duplicates")
            for ref in refs:
                check = check_by_id.get(ref)
                if check is None:
                    errors.append(f"{location} references unknown evidence: {ref}")
                elif check.get("status") != "passed":
                    errors.append(
                        f"{location} references non-passing evidence: {ref} "
                        f"({check.get('status')})"
                    )

    _require_text_list(packet.get("risks"), "risks", errors)

    review = packet.get("human_review")
    if not isinstance(review, dict):
        errors.append("human_review must be an object")
    else:
        _reject_unknown_fields(
            review, V1_HUMAN_REVIEW_FIELDS, "human_review", errors
        )
        if review.get("status") not in V1_HUMAN_REVIEW_STATUSES:
            errors.append(
                "human_review.status must be one of: "
                + ", ".join(sorted(V1_HUMAN_REVIEW_STATUSES))
            )
        _require_text_field(review, "reviewer", "human_review", errors)
        _require_text_field(review, "summary", "human_review", errors)
        _require_sha(
            review.get("reviewed_head_sha"),
            "human_review.reviewed_head_sha",
            errors,
        )
        reviewed_head = review.get("reviewed_head_sha")
        if head_sha is not None and isinstance(reviewed_head, str):
            if SHA_PATTERN.fullmatch(reviewed_head) and reviewed_head.lower() != head_sha:
                errors.append(
                    "human_review.reviewed_head_sha does not match subject.head_sha"
                )

    safety = packet.get("public_safety")
    if not isinstance(safety, dict):
        errors.append("public_safety must be an object")
    else:
        _reject_unknown_fields(
            safety, V1_PUBLIC_SAFETY_FIELDS, "public_safety", errors
        )
        if safety.get("status") not in V1_PUBLIC_SAFETY_STATUSES:
            errors.append(
                "public_safety.status must be one of: "
                + ", ".join(sorted(V1_PUBLIC_SAFETY_STATUSES))
            )
        _require_text_field(safety, "summary", "public_safety", errors)
        _require_sha(
            safety.get("reviewed_head_sha"),
            "public_safety.reviewed_head_sha",
            errors,
        )
        reviewed_head = safety.get("reviewed_head_sha")
        if head_sha is not None and isinstance(reviewed_head, str):
            if SHA_PATTERN.fullmatch(reviewed_head) and reviewed_head.lower() != head_sha:
                errors.append(
                    "public_safety.reviewed_head_sha does not match subject.head_sha"
                )
    if "extensions" in packet and not isinstance(packet["extensions"], dict):
        errors.append("extensions must be an object when present")
    return errors


def validate_packet(packet: dict[str, Any]) -> list[str]:
    """Validate a legacy or v1 receipt while preserving the original API."""
    version = receipt_version(packet)
    if version == "legacy":
        return validate_legacy_packet(packet)
    if version == "v1":
        return validate_v1_packet(packet)
    return ["schema_version is unsupported; omit it for legacy or use 1"]


def review_readiness_errors(packet: dict[str, Any]) -> list[str]:
    """Return v1 conditions that prevent a review-ready verification result."""
    errors: list[str] = []
    checks = packet.get("checks", [])
    if isinstance(checks, list):
        for check in checks:
            if (
                isinstance(check, dict)
                and check.get("required") is True
                and check.get("status") != "passed"
            ):
                errors.append(
                    f"required check is not passing: {check.get('id')} "
                    f"({check.get('status')})"
                )
    review = packet.get("human_review")
    if isinstance(review, dict) and review.get("status") != "approved":
        errors.append("human_review.status must be approved for repository verification")
    safety = packet.get("public_safety")
    if isinstance(safety, dict) and safety.get("status") != "reviewed":
        errors.append("public_safety.status must be reviewed for repository verification")
    return errors


def _run_git(repo: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    command = [
        "git",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.pager=cat",
        "-C",
        str(repo),
        *arguments,
    ]
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout="",
            stderr=f"Git command timed out after {GIT_TIMEOUT_SECONDS} seconds",
        )


def verify_repository(packet: dict[str, Any], repo: Path) -> list[str]:
    """Compare a valid v1 receipt with local, read-only Git state."""
    errors: list[str] = []
    if receipt_version(packet) != "v1":
        return [
            "legacy receipts cannot be repository-verified; migrate to schema_version 1"
        ]
    validation_errors = validate_v1_packet(packet)
    if validation_errors:
        return validation_errors

    repo = repo.resolve()
    if not repo.is_dir():
        return [f"repository path is not a directory: {repo}"]
    inside = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return [f"repository path is not a Git work tree: {repo}"]

    subject = packet["subject"]
    base_sha = subject["base_sha"].lower()
    head_sha = subject["head_sha"].lower()
    for label, revision in (("base", base_sha), ("head", head_sha)):
        exists = _run_git(repo, ["cat-file", "-e", f"{revision}^{{commit}}"])
        if exists.returncode != 0:
            errors.append(f"subject.{label}_sha is not a commit in the repository")
    if errors:
        return errors

    current = _run_git(repo, ["rev-parse", "HEAD"])
    if current.returncode != 0:
        errors.append("could not resolve repository HEAD")
    elif current.stdout.strip().lower() != head_sha:
        errors.append(
            "repository HEAD does not match subject.head_sha "
            f"(current {current.stdout.strip()})"
        )

    status = _run_git(
        repo, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
    )
    if status.returncode != 0:
        errors.append("could not inspect repository work-tree status")
    elif status.stdout:
        errors.append(
            "repository work tree has uncommitted or untracked changes; "
            "verify a clean checkout of subject.head_sha"
        )

    ancestor = _run_git(repo, ["merge-base", "--is-ancestor", base_sha, head_sha])
    if ancestor.returncode == 1:
        errors.append("subject.base_sha is not an ancestor of subject.head_sha")
    elif ancestor.returncode != 0:
        errors.append("could not compare subject base and head revisions")

    diff = _run_git(
        repo,
        ["diff", "--name-only", "--no-renames", "-z", base_sha, head_sha],
    )
    actual_paths: set[str] = set()
    if diff.returncode != 0:
        errors.append("could not list paths changed between subject revisions")
    else:
        actual_paths = {path for path in diff.stdout.split("\0") if path}
        recorded_paths = set(packet["files_touched"])
        missing = sorted(actual_paths - recorded_paths)
        extra = sorted(recorded_paths - actual_paths)
        if missing:
            errors.append("changed paths missing from files_touched: " + ", ".join(missing))
        if extra:
            errors.append("files_touched not present in Git diff: " + ", ".join(extra))

    allowed = set(packet["scope"]["allowed_paths"])
    outside_scope = sorted(actual_paths - allowed)
    if outside_scope:
        errors.append(
            "Git diff includes paths outside scope.allowed_paths: "
            + ", ".join(outside_scope)
        )
    protected = sorted(
        path
        for path in actual_paths
        if _is_protected(path, packet["scope"]["protected_prefixes"])
    )
    if protected:
        errors.append("Git diff includes protected paths: " + ", ".join(protected))

    errors.extend(review_readiness_errors(packet))
    return errors


def _markdown_text(value: Any) -> str:
    """Render supplied text without allowing it to create Markdown structure."""
    normalized = " ".join(str(value).split())
    escaped = html.escape(normalized, quote=False)
    return MARKDOWN_ESCAPE_PATTERN.sub(r"\\\1", escaped)


def _markdown_code(value: Any) -> str:
    """Render a safe CommonMark code span, including values containing backticks."""
    text = " ".join(str(value).splitlines())
    runs = [len(match.group(0)) for match in re.finditer(r"`+", text)]
    delimiter = "`" * (max(runs, default=0) + 1)
    padding = " " if text.startswith(("`", " ")) or text.endswith(("`", " ")) else ""
    return f"{delimiter}{padding}{text}{padding}{delimiter}"


def _markdown_quote(value: Any) -> list[str]:
    lines = str(value).splitlines() or [""]
    return [f"> {_markdown_text(line)}" if line else ">" for line in lines]


def _markdown_list(items: list[str]) -> list[str]:
    return (
        [f"- {_markdown_text(item)}" for item in items]
        if items
        else ["- None recorded."]
    )


def render_v1(packet: dict[str, Any]) -> str:
    """Render a deterministic reviewer-facing v1 receipt."""
    subject = packet["subject"]
    scope = packet["scope"]
    lines = [
        "# EvidenceGate v1 receipt",
        "",
        f"> {BOUNDARY}",
        "",
        "## Summary",
        "",
        *_markdown_quote(packet["summary"]),
        "",
        "## Revision",
        "",
        f"- Base: {_markdown_code(subject['base_sha'])}",
        f"- Head: {_markdown_code(subject['head_sha'])}",
        "",
        "## Recorded scope",
        "",
        "### Files touched",
        "",
        *_markdown_list(packet["files_touched"]),
        "",
        "### Allowed paths",
        "",
        *_markdown_list(scope["allowed_paths"]),
        "",
        "### Protected prefixes",
        "",
        *_markdown_list(scope["protected_prefixes"]),
        "",
        "## Checks",
        "",
    ]
    for check in packet["checks"]:
        requirement = "required" if check["required"] else "optional"
        lines.extend(
            [
                f"- {_markdown_code(check['id'])} "
                f"[{check['status']}; {requirement}] {_markdown_text(check['name'])}",
                f"  - Command: {_markdown_code(check['command'])}",
                f"  - Scope: {_markdown_text(check['scope'])}",
                f"  - Revision: {_markdown_code(check['revision'])}",
                f"  - Recorded result: {_markdown_text(check['summary'])}",
            ]
        )
    lines.extend(["", "## Claims", ""])
    for claim in packet["claims"]:
        refs = ", ".join(_markdown_code(ref) for ref in claim["evidence_refs"])
        lines.extend(
            [
                f"- {_markdown_code(claim['id'])} {_markdown_text(claim['text'])}",
                f"  - Recorded evidence: {refs}",
            ]
        )
    lines.extend(["", "## Residual risks", "", *_markdown_list(packet["risks"])])

    review = packet["human_review"]
    lines.extend(
        [
            "",
            "## Human review",
            "",
            f"- Status: {review['status']}",
            f"- Reviewer: {_markdown_text(review['reviewer'])}",
            f"- Reviewed head: {_markdown_code(review['reviewed_head_sha'])}",
            f"- Summary: {_markdown_text(review['summary'])}",
        ]
    )
    safety = packet["public_safety"]
    lines.extend(
        [
            "",
            "## Public-safety review",
            "",
            f"- Status: {safety['status']}",
            f"- Reviewed head: {_markdown_code(safety['reviewed_head_sha'])}",
            f"- Summary: {_markdown_text(safety['summary'])}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_legacy(packet: dict[str, Any]) -> str:
    """Render the original receipt with an explicit legacy limitation."""
    lines = [
        "# EvidenceGate legacy receipt",
        "",
        "> Legacy format: structural fields only. This receipt is not revision-bound, "
        "claim-linked, or eligible for `verify --repo`.",
        "",
        f"> {BOUNDARY}",
        "",
        "## Summary",
        "",
        *_markdown_quote(packet.get("summary", "")),
        "",
        "## Files touched",
        "",
        *_markdown_list(packet.get("files_touched", [])),
        "",
        "## Commands",
        "",
    ]
    for command in packet.get("commands", []):
        lines.append(
            f"- [{command.get('result')}] {_markdown_code(command.get('command'))}"
        )
    lines.extend(["", "## Tests", ""])
    for test in packet.get("tests", []):
        lines.append(
            f"- [{test.get('status')}] {_markdown_text(test.get('name'))}"
        )
    lines.extend(["", "## Residual risks", "", *_markdown_list(packet.get("risks", []))])
    return "\n".join(lines) + "\n"


def render_packet(packet: dict[str, Any]) -> str:
    errors = validate_packet(packet)
    if errors:
        raise ValueError("cannot render invalid receipt: " + "; ".join(errors))
    version = receipt_version(packet)
    if version == "v1":
        return render_v1(packet)
    return render_legacy(packet)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def _validate_json_value(value: Any, location: str = "$") -> None:
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ValueError(f"unpaired Unicode surrogate is not allowed at {location}")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite JSON number is not allowed at {location}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_json_value(key, f"{location} object key")
            _validate_json_value(item, f"{location}.{key}")


def load_packet(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    size = len(raw)
    if size > MAX_PACKET_BYTES:
        raise ValueError(
            f"packet is {size} bytes; maximum supported size is {MAX_PACKET_BYTES}"
        )
    try:
        text = raw.decode("utf-8")
        data = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise ValueError(f"packet must be UTF-8: {exc}") from exc
    except RecursionError as exc:
        raise ValueError("packet JSON nesting is too deep") from exc
    try:
        _validate_json_value(data)
    except RecursionError as exc:
        raise ValueError("packet JSON nesting is too deep") from exc
    if not isinstance(data, dict):
        raise ValueError("packet must be a JSON object")
    return data


def self_test() -> None:
    good_legacy = {
        "summary": "Added a README and one test.",
        "commands": [{"command": "python3 demo.py --self-test", "result": "passed"}],
        "files_touched": ["README.md", "demo.py"],
        "tests": [{"name": "self-test", "status": "passed"}],
        "risks": ["none"],
        "human_review": {"status": "approved", "reviewer": "maintainer"},
        "public_safety": {"private_data_reviewed": True},
    }
    bad_legacy = dict(good_legacy)
    bad_legacy["human_review"] = {"status": "pending"}
    assert validate_packet(good_legacy) == []
    assert validate_packet(bad_legacy)

    incomplete_legacy = copy.deepcopy(good_legacy)
    incomplete_legacy["tests"][0]["status"] = "pending"
    incomplete_legacy["human_review"] = {"status": "pending"}
    incomplete_legacy["public_safety"] = {"private_data_reviewed": False}
    incomplete_errors = set(validate_packet(incomplete_legacy))
    assert {
        "tests[1] must name a passed check",
        "human_review.status must be approved",
        "public_safety.private_data_reviewed must be true",
    } <= incomplete_errors

    base_sha = "1" * 40
    head_sha = "2" * 40
    v1 = {
        "schema_version": 1,
        "summary": "Changed one synthetic file and recorded one focused check.",
        "subject": {
            "type": "git_change",
            "base_sha": base_sha,
            "head_sha": head_sha,
        },
        "scope": {
            "allowed_paths": ["demo.py"],
            "protected_prefixes": ["private"],
        },
        "files_touched": ["demo.py"],
        "checks": [
            {
                "id": "check:focused",
                "name": "Focused synthetic check",
                "command": "python demo.py --self-test",
                "status": "passed",
                "summary": "The synthetic check passed.",
                "scope": "Synthetic behavior",
                "revision": head_sha,
                "required": True,
            }
        ],
        "claims": [
            {
                "id": "claim:behavior",
                "text": "The synthetic behavior passes its focused check.",
                "evidence_refs": ["check:focused"],
            }
        ],
        "risks": ["This is an in-memory synthetic self-test."],
        "human_review": {
            "status": "approved",
            "reviewer": "synthetic-reviewer",
            "reviewed_head_sha": head_sha,
            "summary": "Simulated review for the self-test.",
        },
        "public_safety": {
            "status": "reviewed",
            "reviewed_head_sha": head_sha,
            "summary": "Confirmed that the self-test is synthetic.",
        },
    }
    assert validate_packet(v1) == []
    assert review_readiness_errors(v1) == []
    assert "# EvidenceGate v1 receipt" in render_packet(v1)

    stale = copy.deepcopy(v1)
    stale["checks"][0]["revision"] = base_sha
    assert validate_packet(stale)

    unsupported = copy.deepcopy(v1)
    unsupported["claims"][0]["evidence_refs"] = ["check:missing"]
    assert validate_packet(unsupported)

    not_ready = copy.deepcopy(v1)
    failed_check = copy.deepcopy(not_ready["checks"][0])
    failed_check["id"] = "check:required-failure"
    failed_check["status"] = "failed"
    failed_check["summary"] = "A required synthetic check failed."
    not_ready["checks"].append(failed_check)
    not_ready["human_review"]["status"] = "changes_requested"
    not_ready["public_safety"]["status"] = "pending"
    assert validate_packet(not_ready) == []
    assert review_readiness_errors(not_ready)


def _print_errors(title: str, errors: list[str]) -> None:
    print(title)
    for error in errors:
        print(f"- {error}")


def _normalize_argv(argv: list[str]) -> list[str]:
    commands = {"validate", "verify", "render"}
    if argv and not argv[0].startswith("-") and argv[0] not in commands:
        return ["validate", *argv]
    return argv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate", help="validate receipt structure and internal references"
    )
    validate_parser.add_argument("path")

    verify_parser = subparsers.add_parser(
        "verify", help="verify a v1 receipt against a local Git repository"
    )
    verify_parser.add_argument("path")
    verify_parser.add_argument("--repo", required=True)

    render_parser = subparsers.add_parser(
        "render", help="render a valid receipt as deterministic Markdown"
    )
    render_parser.add_argument("path")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(_normalize_argv(raw_argv))

    if args.self_test:
        if args.command is not None:
            parser.error("--self-test cannot be combined with a command")
        self_test()
        print("self-test passed")
        return 0
    if args.command is None:
        parser.error("choose validate, verify, or render, or use --self-test")

    try:
        packet = load_packet(Path(args.path))
    except (OSError, ValueError) as exc:
        print(f"Could not load packet: {exc}", file=sys.stderr)
        return 2

    errors = validate_packet(packet)
    if errors:
        _print_errors("FAIL EvidenceGate validation", errors)
        return 1

    version = receipt_version(packet)
    if args.command == "validate":
        if version == "legacy":
            print(
                "PASS EvidenceGate legacy receipt "
                "(structural only; not revision-bound or repository-verified)"
            )
        else:
            print(
                "PASS EvidenceGate v1 receipt structure "
                "(repository state not checked)"
            )
        return 0

    if args.command == "verify":
        verify_errors = verify_repository(packet, Path(args.repo))
        if verify_errors:
            _print_errors("FAIL EvidenceGate repository verification", verify_errors)
            return 1
        print("PASS EvidenceGate v1 repository verification")
        return 0

    print(render_packet(packet), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
