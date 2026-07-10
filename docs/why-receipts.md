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

The second command should exit `1` and report:

```text
FAIL EvidenceGate
- tests[1] must name a passed check
- human_review.status must be approved
- public_safety.private_data_reviewed must be true
```

The failure is useful. It prevents an unfinished receipt from looking ready for
trust or publication.

## The Copyable Pattern

Start with the [receipt template](../templates/agent-run-receipt.template.json),
then complete it from evidence after the final edit:

1. Summarize the accepted change, not the original plan.
2. Record the commands that actually ran and their results.
3. Compare `files_touched` with the real diff.
4. Name the checks that passed after the final edit.
5. State residual risk honestly, including skipped environments or coverage.
6. Have a human inspect the diff, verify the receipt, and accept the risk.
7. Complete public-safety review before copying the receipt into a public place.
8. Run EvidenceGate and attach the receipt to the handoff, pull request, or
   release record where it will help a reviewer.

Use the [review checklist](review-checklist.md) for the human verification step.

## What A Valid Receipt Proves

EvidenceGate checks that the receipt contains:

- a non-empty summary
- recorded commands with accepted result values
- a list of touched files
- named checks marked as passed
- stated residual risk
- human approval
- completed public-safety review

That is a useful structural gate. It makes missing review evidence visible.

## What It Does Not Prove

A valid receipt does not prove that:

- the recorded commands actually ran
- the file list matches the diff
- the chosen tests were sufficient
- the change is correct, secure, or valuable
- the reviewer understood every consequence
- no unknown risk remains

A polished but dishonest receipt can still pass a structural validator. The
human reviewer must compare it with the diff, command output, and actual result.
EvidenceGate makes accountability easier to inspect; it does not automate
accountability away.

## When To Use It

Receipts are most useful for substantive AI-assisted changes, reviewer
handoffs, releases, and public-candidate work. A one-line typo fix may not need
the full pattern. Use the smallest receipt that helps the next person decide
whether the evidence is sufficient.
