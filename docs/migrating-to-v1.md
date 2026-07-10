# Migrating A Legacy Receipt To V1

Legacy receipts remain valid for structural checks. They are labelled legacy
and cannot use `verify --repo` because they do not identify a revision or link
claims to evidence.

To migrate one:

1. Add `"schema_version": 1`.
2. Add `subject.type`, `subject.base_sha`, and `subject.head_sha` using full
   40-character commit SHAs.
3. Add `scope.allowed_paths` as exact Git paths and
   `scope.protected_prefixes` as relative path prefixes.
4. Keep `files_touched`, then confirm it matches the Git diff from base to
   head.
5. Replace `commands` and `tests` with `checks`. Give every check a unique ID,
   command, `passed` / `failed` / `skipped` / `unknown` status, result summary,
   scope, recorded revision, and `required` flag.
6. Add bounded `claims` whose `evidence_refs` name passing check IDs.
7. Keep `risks`, including skipped or unknown coverage.
8. Add the reviewed head and summary to `human_review`.
9. Replace the legacy public-safety boolean with a status, reviewed head, and
   summary.
10. Remove undeclared fields. If non-authoritative metadata must travel with the
    receipt, place it under the optional `extensions` object; v1 validation,
    verification, and rendering deliberately ignore its contents.

Start from
[`templates/agent-run-receipt-v1.template.json`](../templates/agent-run-receipt-v1.template.json)
and compare it with
[`examples/v1-review-ready.json`](../examples/v1-review-ready.json).
The [JSON Schema](../schemas/agent-run-receipt-v1.schema.json) and portable
[conformance corpus](../conformance/v1/README.md) define the public v1 contract.

Validate before using Git state:

```sh
python3 evidencegate.py validate path/to/receipt.json
```

Then compare it with the reviewed checkout:

```sh
python3 evidencegate.py verify path/to/receipt.json --repo /path/to/repository
```

Migration strengthens deterministic consistency checks. It does not turn the
receipt into proof that recorded commands ran or that supplied evidence and
review identities are authentic.
