# EvidenceGate

A tiny CLI for checking whether an AI-assisted run has enough evidence for a
human reviewer.

It validates a JSON packet that lists what was run, which files changed, what
checks passed, what risks remain, and whether a human has approved the result.

## Why It Exists

AI-assisted work should leave a receipt. EvidenceGate is a small pattern for
turning an agent run into something a maintainer can review: commands, files,
checks, risks, human approval, and public-safety review.

## Run

```sh
python3 evidencegate.py examples/good-run.json
python3 evidencegate.py examples/agent-run-receipt.json
python3 evidencegate.py examples/python-cli-bugfix.json
python3 evidencegate.py examples/browser-qa-regression.json
python3 evidencegate.py examples/public-safety-publication.json
python3 evidencegate.py --self-test
```

Expected result:

```text
PASS EvidenceGate
```

## Agent Run Receipts

Use an Agent Run Receipt after an AI-assisted coding session to leave a compact
review trail:

- `templates/agent-run-receipt.template.json` is a copyable starting point.
- `examples/agent-run-receipt.json` is a valid filled example.
- `examples/python-cli-bugfix.json` is a more realistic bug-fix receipt.
- `examples/browser-qa-regression.json` shows a browser QA regression receipt.
- `examples/public-safety-publication.json` shows a public-safe publication receipt.
- `docs/review-checklist.md` is the human review checklist.

The receipt is intentionally boring: what changed, which commands ran, which
files changed, which checks passed, what risks remain, who reviewed it, and
whether public-safety review happened.

## How These Fit Together

EvidenceGate is one piece of a small public toolkit:

- [Public Repo Safety Kit](https://github.com/TheDarkniteFalls/public-repo-safety-kit)
  checks a public-candidate repo before publishing.
- EvidenceGate records the evidence and checks behind an AI-assisted change.
- [Local Model Reliability Example](https://github.com/TheDarkniteFalls/local-model-reliability-example)
  validates structured model output before trusting it.
- [Context Boundary Examples](https://github.com/TheDarkniteFalls/context-boundary-examples)
  checks whether an answer stays inside supplied evidence.
- [Green-Spine QA Pattern](https://github.com/TheDarkniteFalls/green-spine-qa-pattern)
  bundles the important path behind one repeatable command.

## Packet Shape

A packet is intentionally small:

- `summary`: what changed.
- `commands`: commands run and their results.
- `files_touched`: changed files.
- `tests`: validation checks and pass/fail status.
- `risks`: known residual risk, or `none`.
- `human_review`: approval state.
- `public_safety`: whether private data was reviewed.

## Scope

This is a minimal pattern, not a platform. It is useful when a reviewer needs a
compact receipt before trusting an agent-assisted change.

## Quality Checks

```sh
python3 evidencegate.py --self-test
python3 evidencegate.py examples/good-run.json
python3 evidencegate.py examples/agent-run-receipt.json
python3 evidencegate.py examples/python-cli-bugfix.json
python3 evidencegate.py examples/browser-qa-regression.json
python3 evidencegate.py examples/public-safety-publication.json
python3 -m py_compile evidencegate.py
```
