#!/usr/bin/env python3
"""Validate EvidenceGate's unsigned in-toto attestation profile v0."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import evidencegate  # noqa: E402


STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = (
    "https://github.com/TheDarkniteFalls/evidencegate/attestation/v0"
)
PROFILE = "evidencegate_attestation_v0"
RECEIPT_MEDIA_TYPE = "application/vnd.evidencegate.receipt.v1+json"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MAX_VALIDITY = timedelta(hours=24)

TOP_FIELDS = {"_type", "subject", "predicateType", "predicate"}
SUBJECT_FIELDS = {"name", "digest"}
PREDICATE_FIELDS = {
    "profile",
    "receipt",
    "base_sha",
    "head_sha",
    "issued_at",
    "expires_at",
    "claimed_issuer",
}
RECEIPT_FIELDS = {"media_type", "sha256"}


def _unknown_fields(value: dict[str, Any], allowed: set[str], location: str) -> list[str]:
    return [
        f"{location}.{field} is not defined by the attestation profile v0"
        for field in sorted(set(value) - allowed)
    ]


def _parse_utc_timestamp(value: Any, location: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or UTC_TIMESTAMP_PATTERN.fullmatch(value) is None:
        errors.append(f"{location} must be an RFC 3339 UTC timestamp ending in Z")
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        errors.append(f"{location} is not a real UTC date and time")
        return None


def validate_attestation(
    statement: dict[str, Any],
    receipt_path: Path,
    *,
    expected_subject: str,
    expected_issuer: str,
    at_time: datetime,
) -> list[str]:
    """Check statement structure, policy, raw receipt digest, and receipt subject."""
    errors = _unknown_fields(statement, TOP_FIELDS, "statement")
    if statement.get("_type") != STATEMENT_TYPE:
        errors.append(f"statement._type must be {STATEMENT_TYPE}")
    if statement.get("predicateType") != PREDICATE_TYPE:
        errors.append(f"statement.predicateType must be {PREDICATE_TYPE}")

    subjects = statement.get("subject")
    subject: dict[str, Any] | None = None
    if not isinstance(subjects, list) or len(subjects) != 1:
        errors.append("statement.subject must contain exactly one Git subject")
    elif not isinstance(subjects[0], dict):
        errors.append("statement.subject[1] must be an object")
    else:
        subject = subjects[0]
        errors.extend(_unknown_fields(subject, SUBJECT_FIELDS, "statement.subject[1]"))
        if subject.get("name") != expected_subject:
            errors.append("statement.subject[1].name does not match expected subject")
        digest = subject.get("digest")
        if not isinstance(digest, dict) or set(digest) != {"gitCommit"}:
            errors.append("statement.subject[1].digest must contain only gitCommit")
        elif (
            not isinstance(digest.get("gitCommit"), str)
            or evidencegate.SHA_PATTERN.fullmatch(digest["gitCommit"]) is None
        ):
            errors.append("statement.subject[1].digest.gitCommit must be a full Git SHA")

    predicate = statement.get("predicate")
    if not isinstance(predicate, dict):
        errors.append("statement.predicate must be an object")
        return errors
    errors.extend(_unknown_fields(predicate, PREDICATE_FIELDS, "statement.predicate"))
    if predicate.get("profile") != PROFILE:
        errors.append(f"statement.predicate.profile must be {PROFILE}")
    if predicate.get("claimed_issuer") != expected_issuer:
        errors.append("statement.predicate.claimed_issuer does not match expected issuer")

    for field in ("base_sha", "head_sha"):
        value = predicate.get(field)
        if not isinstance(value, str) or evidencegate.SHA_PATTERN.fullmatch(value) is None:
            errors.append(f"statement.predicate.{field} must be a full Git SHA")

    issued = _parse_utc_timestamp(
        predicate.get("issued_at"), "statement.predicate.issued_at", errors
    )
    expires = _parse_utc_timestamp(
        predicate.get("expires_at"), "statement.predicate.expires_at", errors
    )
    if issued is not None and expires is not None:
        if expires <= issued:
            errors.append("statement validity window must end after it starts")
        elif expires - issued > MAX_VALIDITY:
            errors.append("statement validity window must not exceed 24 hours")
        if at_time.tzinfo is None or at_time.utcoffset() is None:
            errors.append("policy evaluation time must be timezone-aware UTC")
        else:
            if at_time < issued:
                errors.append("statement is not valid yet at the policy evaluation time")
            if at_time >= expires:
                errors.append("statement is expired at the policy evaluation time")

    try:
        receipt_packet = evidencegate.load_packet(receipt_path)
        receipt_bytes = receipt_path.read_bytes()
    except (OSError, ValueError) as exc:
        errors.append(f"supplied receipt cannot be loaded: {exc}")
        return errors

    receipt = predicate.get("receipt")
    if not isinstance(receipt, dict):
        errors.append("statement.predicate.receipt must be an object")
    else:
        errors.extend(
            _unknown_fields(receipt, RECEIPT_FIELDS, "statement.predicate.receipt")
        )
        if receipt.get("media_type") != RECEIPT_MEDIA_TYPE:
            errors.append(
                f"statement.predicate.receipt.media_type must be {RECEIPT_MEDIA_TYPE}"
            )
        digest = receipt.get("sha256")
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            errors.append("statement.predicate.receipt.sha256 must be lowercase SHA-256")
        else:
            actual_digest = hashlib.sha256(receipt_bytes).hexdigest()
            if digest != actual_digest:
                errors.append("statement receipt digest does not match supplied receipt bytes")

    if evidencegate.receipt_version(receipt_packet) != "v1":
        errors.append("supplied receipt must use EvidenceGate schema_version 1")
        return errors
    receipt_errors = evidencegate.validate_v1_packet(receipt_packet)
    errors.extend(f"supplied receipt: {error}" for error in receipt_errors)
    if not receipt_errors:
        receipt_subject = receipt_packet["subject"]
        if predicate.get("base_sha") != receipt_subject["base_sha"]:
            errors.append("statement base_sha does not match supplied receipt")
        if predicate.get("head_sha") != receipt_subject["head_sha"]:
            errors.append("statement head_sha does not match supplied receipt")
        if subject is not None and isinstance(subject.get("digest"), dict):
            if subject["digest"].get("gitCommit") != receipt_subject["head_sha"]:
                errors.append("statement subject digest does not match supplied receipt head")
    return errors


def _default_time() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("statement", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expected-subject", required=True)
    parser.add_argument("--expected-issuer", required=True)
    parser.add_argument(
        "--at-time",
        help="RFC 3339 UTC policy time; defaults to the current UTC time",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        statement = evidencegate.load_packet(args.statement)
        if args.at_time:
            parsed: list[str] = []
            at_time = _parse_utc_timestamp(args.at_time, "--at-time", parsed)
            if parsed or at_time is None:
                raise ValueError("; ".join(parsed))
        else:
            at_time = _default_time()
        errors = validate_attestation(
            statement,
            args.receipt,
            expected_subject=args.expected_subject,
            expected_issuer=args.expected_issuer,
            at_time=at_time,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL EvidenceGate attestation profile v0: {exc}")
        return 1
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print("PASS EvidenceGate attestation profile v0 contract (UNAUTHENTICATED)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
