#!/usr/bin/env python3
"""Create an unsigned EvidenceGate in-toto Statement from a valid v1 receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import evidencegate  # noqa: E402
from attestation_profile import (  # noqa: E402
    PREDICATE_TYPE,
    PROFILE,
    RECEIPT_MEDIA_TYPE,
    STATEMENT_TYPE,
    validate_attestation,
)


def _timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValueError("--issued-at must be an RFC 3339 UTC timestamp ending in Z") from exc


def create_statement(
    receipt_path: Path,
    *,
    subject_name: str,
    claimed_issuer: str,
    issued_at: datetime,
    valid_for_minutes: int,
) -> dict[str, Any]:
    if not subject_name.strip():
        raise ValueError("subject name must be non-empty")
    if not claimed_issuer.strip():
        raise ValueError("claimed issuer must be non-empty")
    if not 1 <= valid_for_minutes <= 24 * 60:
        raise ValueError("validity must be from 1 to 1440 minutes")
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise ValueError("issued_at must be timezone-aware")
    receipt = evidencegate.load_packet(receipt_path)
    if evidencegate.receipt_version(receipt) != "v1":
        raise ValueError("receipt must use EvidenceGate schema_version 1")
    errors = evidencegate.validate_v1_packet(receipt)
    if errors:
        raise ValueError("receipt is invalid: " + "; ".join(errors))
    raw_receipt = receipt_path.read_bytes()
    head_sha = receipt["subject"]["head_sha"]
    expires_at = issued_at.astimezone(timezone.utc) + timedelta(
        minutes=valid_for_minutes
    )
    issued_at = issued_at.astimezone(timezone.utc)
    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "name": subject_name,
                "digest": {"gitCommit": head_sha},
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "profile": PROFILE,
            "receipt": {
                "media_type": RECEIPT_MEDIA_TYPE,
                "sha256": hashlib.sha256(raw_receipt).hexdigest(),
            },
            "base_sha": receipt["subject"]["base_sha"],
            "head_sha": head_sha,
            "issued_at": issued_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "claimed_issuer": claimed_issuer,
        },
    }


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--claimed-issuer", required=True)
    parser.add_argument("--issued-at")
    parser.add_argument("--valid-for-minutes", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        if args.output.resolve() == args.receipt.resolve():
            raise ValueError("output must not overwrite the receipt")
        issued_at = _timestamp(args.issued_at)
        statement = create_statement(
            args.receipt,
            subject_name=args.subject,
            claimed_issuer=args.claimed_issuer,
            issued_at=issued_at,
            valid_for_minutes=args.valid_for_minutes,
        )
        errors = validate_attestation(
            statement,
            args.receipt,
            expected_subject=args.subject,
            expected_issuer=args.claimed_issuer,
            at_time=issued_at,
        )
        if errors:
            raise ValueError("generated statement failed validation: " + "; ".join(errors))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(statement, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"FAIL unsigned attestation statement creation: {exc}")
        return 1
    print(f"PASS wrote unsigned attestation statement: {args.output}")
    print("UNAUTHENTICATED: wrap and verify this statement with standard tooling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
