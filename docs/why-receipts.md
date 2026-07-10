# Why AI-Assisted Work Should Leave a Receipt

AI-assisted work is easier to review when the final result includes a compact
record of what changed, what was checked, what remains uncertain, and who
accepted it.

This guide is for maintainers, solo builders, and coding-agent users who need a
review record that is smaller and more useful than a complete chat transcript.

## Chat History Is Not A Review Record

A chat transcript can explain how work unfolded, but it does not reliably show
the final state:

- Commands may have run before the last edit.
- Proposed file changes may differ from the real diff.
- Failed attempts can be mixed together with accepted work.
- Remaining risks and skipped checks are easy to overlook.
- A suggestion or summary does not prove that a human approved the result.
- Private context in a chat may be unsafe to copy into a public review.

A receipt does not replace the transcript when the reasoning matters. It gives
the reviewer a final, deliberately small record to verify.

## Good Versus Incomplete

The original examples in this section use EvidenceGate's legacy receipt
format. They remain useful for comparing a complete structural record with an
incomplete one, but they are not revision-bound or eligible for repository
verification. See [Migrating a Legacy Receipt to V1](migrating-to-v1.md) for
the stronger format.

Compare these synthetic examples:

- [Complete bug-fix receipt](../examples/python-cli-bugfix.json)
- [Incomplete agent-run receipt](../examples/incomplete-agent-run.json)

| Review question | Complete receipt | Incomplete receipt |
| --- | --- | --- |
| What changed? | Names a specific bug and regression check | Names the intended fix but says verification is pending |
| What ran? | Lists the focused test, smoke command, and receipt validation | Lists only a syntax check |
| Did the important test pass? | Yes | No; the regression test was not run |
| Are remaining risks visible? | Yes | Yes, but they have not been accepted |
| Did a human approve it? | Yes | No |
| Was public-safety review completed? | Yes | No |
| EvidenceGate result | `PASS` | Expected `FAIL` |

Run both:

```sh
python3 evidencegate.py examples/python-cli-bugfix.json
python3 evidencegate.py examples/incomplete-agent-run.json
```

The first command reports a clearly labelled legacy structural pass. The
second command should exit `1` and report:

```text
FAIL EvidenceGate validation
- tests[1] must name a passed check
- human_review.status must be approved
- public_safety.private_data_reviewed must be true
```

The failure is useful. It prevents an unfinished receipt from looking ready for
trust or publication.

## The Copyable Pattern

For new work, start with the [v1 receipt
template](../templates/agent-run-receipt-v1.template.json), then complete it
from evidence after the final edit:

1. Summarize the accepted change, not the original plan.
2. Record the exact base and final head commits plus the allowed and protected
   path scope.
3. Compare `files_touched` with the real diff.
4. Record checks against the final head and preserve passed, failed, skipped,
   and unknown results.
5. Link bounded claims to named passing checks.
6. State residual risk honestly, including skipped environments or coverage.
7. Have a human inspect the diff, real outputs, receipt, and remaining risk.
8. Complete public-safety review against the same head.
9. Run `verify --repo` and attach the receipt where it will help a reviewer.

Use the [review checklist](review-checklist.md) for the human verification step.

## What A Valid Receipt Establishes

Legacy validation checks that the original receipt contains its required
structural fields. V1 validation additionally checks revision and evidence
relationships inside the supplied JSON. V1 repository verification establishes
that, for the supplied receipt and local checkout:

- the named commits exist, local `HEAD` matches the recorded head, and the
  checkout has no uncommitted or untracked changes;
- the Git diff's paths match `files_touched`, stay inside the exact allowed
  paths, and avoid protected prefixes;
- checks, claims, and evidence references are internally consistent;
- required checks are recorded as passing; and
- human and public-safety review are recorded against the same head.

That is a useful deterministic consistency gate. It makes stale evidence,
unsupported claims, path drift, and missing review state visible.

## What It Does Not Prove

A valid receipt does not prove that:

- the recorded commands actually ran
- supplied command output, evidence, receipts, or reviewer identities are
  authentic
- the chosen tests were sufficient
- linked evidence semantically proves a claim
- the change is correct, secure, authorized, or valuable
- the reviewer understood every consequence
- no unknown risk remains
- the repository is safe to publish

A polished but dishonest receipt can still pass a structural validator. The
v1 verifier catches more mismatches, but a coordinated or fabricated receipt
can still mislead it. The human reviewer must compare the receipt with the
complete diff, actual command output, and observed result. EvidenceGate makes
accountability easier to inspect; it does not automate accountability away or
authorize publication.

## When To Use It

Receipts are most useful for substantive AI-assisted changes, reviewer
handoffs, releases, and public-candidate work. A one-line typo fix may not need
the full pattern. Use the smallest receipt that helps the next person decide
whether the evidence is sufficient.
