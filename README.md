# EvidenceGate

AI-assisted work should leave a receipt.

EvidenceGate is a small public pattern for human-reviewed agent work. A receipt
records what changed, what was checked, what remains risky, and who reviewed
it. The v1 format binds that record to one Git revision and links bounded
claims to named checks.

The CLI uses only the Python standard library. It does not run the commands in
a receipt or make publication decisions.

## Quick Start

Run the complete v1 lifecycle against a temporary synthetic Git repository:

```sh
python3 -B examples/run-v1-reference.py
```

Expected result:

```text
PASS focused_check
PASS receipt_structure
PASS repository_verification
PASS stale_head_rejected
PASS omitted_path_rejected
PASS protected_path_rejected
PASS v1_reference_run
```

The reference run creates real base and head commits, runs a focused check,
writes a detached receipt outside the synthetic repository, verifies it, and
then proves that three known-bad variants fail. It uses no model or network and
deletes the temporary files afterward. Human and public-safety decisions are
prominently labelled as simulated; the passing demo does not authenticate
them.

## Validate And Render A Static Receipt

Validate the v1 shape and its internal evidence references:

```sh
python3 evidencegate.py validate examples/v1-review-ready.json
```

Expected result:

```text
PASS EvidenceGate v1 receipt structure (repository state not checked)
```

Render the same supplied record as deterministic Markdown:

```sh
python3 evidencegate.py render examples/v1-review-ready.json
```

To compare a completed receipt with a real local checkout, copy the [v1
template](templates/agent-run-receipt-v1.template.json), replace its synthetic
SHAs and fields with the reviewed change, then run:

```sh
python3 evidencegate.py verify path/to/receipt.json --repo /path/to/repository
```

Expected result for a review-ready receipt that matches the checkout:

```text
PASS EvidenceGate v1 repository verification
```

The checked-in JSON examples use obviously synthetic SHAs, so they demonstrate
`validate` and `render`; the reference run demonstrates `verify --repo` end to
end with actual temporary commits.

## Three Operations

- `validate` checks the selected receipt format and, for v1, unique IDs,
  revision consistency, status values, scope, and claim-to-check references.
- `verify --repo` accepts only v1 receipts. It adds read-only Git checks for
  the current head, a clean work tree, base/head ancestry, exact changed paths,
  allowed paths, protected prefixes, required passing checks, human approval,
  and completed public-safety review.
- `render` turns a valid legacy or v1 receipt into deterministic Markdown. It
  preserves `passed`, `failed`, `skipped`, and `unknown` rather than hiding
  uncertainty.

The original shorthand remains supported:

```sh
python3 evidencegate.py examples/good-run.json
```

It now says explicitly that the original format is legacy, structural-only,
and not eligible for repository verification.

## V1 Receipt Shape

A v1 receipt records:

- `schema_version`: currently `1`.
- `subject`: full base and head Git commit SHAs.
- `scope`: exact allowed paths and protected path prefixes.
- `files_touched`: the paths the receipt says changed.
- `checks`: uniquely identified, caller-recorded commands, statuses, summaries,
  scopes, revisions, and whether each check is required.
- `claims`: bounded statements linked to passing check IDs.
- `risks`: known residual risks, including skipped environments or coverage.
- `human_review`: reviewer decision and reviewed head.
- `public_safety`: public/private-data review state and reviewed head.

See the [review-ready synthetic example](examples/v1-review-ready.json), the
[v1 template](templates/agent-run-receipt-v1.template.json), and the concise
[migration note](docs/migrating-to-v1.md).

Negative fixtures make important failures visible:

- [stale evidence](examples/v1-stale-evidence.json) targets an older revision;
- [unsupported claim](examples/v1-unsupported-claim.json) cites a missing check;
- [not review-ready](examples/v1-not-review-ready.json) preserves a failed
  required check, requested changes, and pending public-safety review.

## Legacy Receipts

The original examples and
[`agent-run-receipt.template.json`](templates/agent-run-receipt.template.json)
remain supported as the **legacy format**. They validate field presence only.
They have no `schema_version`, revision identity, evidence IDs, or Git-state
comparison, and `verify --repo` refuses them rather than implying stronger
assurance.

Existing legacy examples include:

- [good-run.json](examples/good-run.json)
- [agent-run-receipt.json](examples/agent-run-receipt.json)
- [python-cli-bugfix.json](examples/python-cli-bugfix.json)
- [browser-qa-regression.json](examples/browser-qa-regression.json)
- [public-safety-publication.json](examples/public-safety-publication.json)
- [incomplete-agent-run.json](examples/incomplete-agent-run.json), an expected
  validation failure covered by the self-test

## What Repository Verification Establishes

For the supplied receipt and local checkout, a pass establishes that:

- the named commits exist, the base is an ancestor of the head, and local
  `HEAD` equals the recorded head with no uncommitted or untracked changes;
- the recorded touched paths exactly match `git diff --name-only --no-renames`
  between those commits;
- the actual diff stays inside the exact allowed paths and outside protected
  prefixes;
- check IDs and claim references are internally consistent, claims cite only
  passing checks, and all required checks are recorded as passing;
- the recorded check, human-review, and public-safety revisions match the
  receipt head; and
- human review is recorded as approved and public-safety review as completed.

## What It Does Not Establish

EvidenceGate does not:

- run or reproduce recorded commands;
- authenticate evidence, command output, receipts, or reviewer identities;
- prove that the file list or receipt was honestly produced before comparison;
- judge whether tests are sufficient or claims are semantically true;
- prove correctness, security, usefulness, or absence of unknown risk;
- scan repository history for secrets or private material; or
- approve, publish, push, merge, release, or authorize any external action.

The verifier catches deterministic mismatches. A human still compares the
receipt with command output, the complete diff, the actual result, and the
remaining risk. Use the [review checklist](docs/review-checklist.md) for that
decision.

## How These Fit Together

EvidenceGate is one piece of a small public toolkit:

- [Public Repo Safety Kit](https://github.com/TheDarkniteFalls/public-repo-safety-kit)
  checks a public-candidate repo before publishing.
- [Local Model Reliability Example](https://github.com/TheDarkniteFalls/local-model-reliability-example)
  validates structured model output and protected-path boundaries before
  trusting it.
- [Context Boundary Examples](https://github.com/TheDarkniteFalls/context-boundary-examples)
  checks whether an answer stays inside supplied evidence.
- [Green-Spine QA Pattern](https://github.com/TheDarkniteFalls/green-spine-qa-pattern)
  bundles the important path behind one repeatable command.
- [Codex Project Instructions Starter](https://github.com/TheDarkniteFalls/codex-project-instructions-starter)
  gives coding agents clear project rules before they work.

## Scope

This is a receipt validator and local consistency checker, not an attestation
system, policy engine, sandbox, hosted platform, or autonomous approval system.
All checked-in examples are synthetic.

## Quality Checks

```sh
python3 -B evidencegate.py --self-test
python3 -B -m unittest discover -s tests -v
python3 -B examples/run-v1-reference.py
python3 -B evidencegate.py validate examples/v1-review-ready.json
python3 -B evidencegate.py render examples/v1-review-ready.json
python3 -B evidencegate.py examples/good-run.json
python3 -B evidencegate.py examples/agent-run-receipt.json
python3 -B evidencegate.py examples/python-cli-bugfix.json
python3 -B evidencegate.py examples/browser-qa-regression.json
python3 -B evidencegate.py examples/public-safety-publication.json
```
