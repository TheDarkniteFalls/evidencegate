# Agent Run Receipt Review Checklist

Use this checklist before trusting or publishing an AI-assisted change.
EvidenceGate can expose deterministic mismatches; it cannot make the review
decision for you.

## Revision And Scope

- The receipt names the intended base and the exact final head commit.
- The allowed paths match the authority granted for this change.
- Protected prefixes cover private, credential, repository-control, and other
  out-of-scope locations relevant to the project.
- `files_touched` matches the complete Git diff, including new and deleted
  files.
- The checkout used for verification has no uncommitted or untracked changes.
- No edit occurred after the recorded checks or human review.

## Checks And Claims

- Every recorded command is one that actually ran against the receipt head.
- Required checks are relevant to the acceptance criteria, not merely easy
  checks that happen to pass.
- Failed, skipped, and unknown checks remain visible with useful explanations.
- Each material claim cites a named passing check that actually supports it.
- Passing syntax, lint, or receipt validation is not presented as proof of
  behavior it did not exercise.
- Residual risks name skipped environments, incomplete coverage, and known
  uncertainty honestly.

## Human Review

- A human reviewed the complete diff and actual outputs, not only the receipt
  or generated summary.
- The reviewer confirmed that the receipt describes the final head revision.
- The reviewer checked the allowed paths, touched paths, evidence references,
  and remaining risk.
- `approved` means the named human accepted the recorded revision; it is not an
  authentication mechanism or standing authority for later revisions.

## Public Safety

- Public-safety review covers the exact head named in the receipt.
- No credentials, private logs, connector exports, personal notes, local
  absolute paths, or raw private data are included.
- Examples and fixtures use fake or synthetic data.
- Repository history, license, dependency, and publication-policy review are
  completed separately when relevant.
- A passing receipt is never treated as permission to push or publish.

## EvidenceGate Commands

Check v1 structure and evidence references:

```sh
python3 evidencegate.py validate path/to/receipt.json
```

Render the supplied record for review:

```sh
python3 evidencegate.py render path/to/receipt.json
```

Compare a review-ready v1 receipt with a local checkout:

```sh
python3 evidencegate.py verify path/to/receipt.json --repo /path/to/repository
```

Expected verification output:

```text
PASS EvidenceGate v1 repository verification
```

After a pass, still inspect the diff, real command output, public-safety scan,
and remaining risks. EvidenceGate does not run commands, authenticate records,
prove correctness or security, or authorize publication.
