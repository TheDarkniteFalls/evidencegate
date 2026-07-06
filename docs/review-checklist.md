# Agent Run Receipt Review Checklist

Use this checklist before trusting or publishing an AI-assisted change.

## Receipt

- The summary says what changed without hiding the AI-assisted nature of the
  work.
- The commands list includes the important checks that were actually run.
- The files touched list matches the real diff.
- Every test listed as passed was run after the final edit.
- Risks are named honestly, or the receipt says `none` when there is no known
  residual risk.

## Human Review

- A human reviewed the diff, not just the generated summary.
- The reviewer checked that the commands and files in the receipt are accurate.
- The reviewer accepted the remaining risk.

## Public Safety

- No credentials, private logs, connector exports, personal notes, or raw
  private data are included.
- Examples use fake or synthetic data.
- Public-facing files explain scope and limitations.

## EvidenceGate Check

Run:

```sh
python3 evidencegate.py examples/agent-run-receipt.json
```

Expected output:

```text
PASS EvidenceGate
```
