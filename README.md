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
python3 evidencegate.py --self-test
```

Expected result:

```text
PASS EvidenceGate
```

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
python3 -m py_compile evidencegate.py
```
