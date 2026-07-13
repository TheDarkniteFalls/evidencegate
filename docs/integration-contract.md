# EvidenceGate CLI Integration Contract

EvidenceGate v0.1 exposes one stable JSON result shape for `validate` and
`verify`. Integrations should branch on `ok`, exit status, and finding `code`.
Human-readable finding messages may become clearer without a contract change.

## JSON Results

```sh
evidencegate validate receipt.json --format json
evidencegate verify receipt.json --repo . --format json
```

Every result uses `evidencegate_cli_result_v1` and contains:

- `operation`: `validate` or `verify`;
- `ok`: whether the requested gate passed;
- `receipt_version`: `legacy`, `v1`, `unsupported`, or `null` when loading failed;
- `repository_checked`: whether local Git verification actually ran;
- `summary`: a concise human-readable outcome;
- `findings`: stable codes paired with explanatory messages; and
- `boundary`: the trust limitation that applies to every result.

The machine-readable shape is defined by
[`schemas/cli-result-v1.schema.json`](../schemas/cli-result-v1.schema.json).
The receipt itself is never copied into the result.

## Exit Status

| Status | Meaning |
| ---: | --- |
| `0` | The requested validation or verification passed |
| `1` | The receipt or repository produced one or more findings |
| `2` | The receipt could not be read or parsed |

Argument errors remain ordinary command-line usage errors.

## Stable Finding Codes

| Code | Consumer response |
| --- | --- |
| `packet_load_error` | Fix file access or strict JSON parsing before continuing |
| `receipt_version_invalid` | Migrate to a supported receipt version |
| `receipt_structure_invalid` | Fix required fields or unsupported content |
| `receipt_revision_invalid` | Rebuild evidence against the exact head revision |
| `receipt_scope_invalid` | Correct recorded paths and protected boundaries |
| `receipt_evidence_invalid` | Repair checks, claims, IDs, or evidence references |
| `receipt_not_verifiable` | Migrate a legacy receipt to v1 |
| `receipt_review_not_ready` | Complete required checks and reviews |
| `repository_unavailable` | Supply a usable local Git checkout |
| `repository_revision_mismatch` | Check out the receipt's exact head and ancestry |
| `repository_dirty` | Verify from a clean checkout |
| `repository_diff_mismatch` | Reconcile the receipt with the full Git diff |
| `repository_scope_violation` | Stop and review out-of-scope or protected changes |
| `repository_inspection_failed` | Resolve the Git inspection failure before trusting the result |

The portable conformance manifest names expected codes for negative fixtures:
[`conformance/v1/manifest.json`](../conformance/v1/manifest.json).

## Copyable GitHub Actions Recipe

After the `v0.1.0` tag is published, a consuming repository can pin the tool,
validate a supplied receipt, and retain the JSON result as an ordinary workflow
artifact. Before that tag exists, replace it with a reviewed full commit SHA
rather than using `main`.

```yaml
name: evidencegate

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate-receipt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7
        with:
          fetch-depth: 0
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
        with:
          python-version: "3.12"
      - run: >-
          python -m pip install
          "evidencegate @ git+https://github.com/TheDarkniteFalls/evidencegate.git@v0.1.0"
      - run: >-
          evidencegate validate evidence/agent-run-receipt.json
          --format json > evidencegate-result.json
      - if: always()
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: evidencegate-result
          path: evidencegate-result.json
```

This copyable job checks receipt structure and internal evidence references; it
does not compare the receipt with repository state. A `verify --repo` CI job
must instead receive a detached receipt from an earlier trusted step, check out
its exact head revision with full history, and preserve the receipt outside the
checkout so it does not create a self-reference problem. That producer is
workflow-specific, so EvidenceGate does not pretend one generic recipe can
create it safely.

Neither form reruns arbitrary commands recorded inside a receipt, authenticates
a reviewer, or authorizes a merge or publication.
