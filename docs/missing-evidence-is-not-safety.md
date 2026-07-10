# Missing Evidence Is Not Safety

## Thesis

Agent-audit metrics can create false assurance when refused, failed, empty, or
abstained evaluations disappear from the denominator or are converted into a
benign score. Missing evidence is not evidence of safety. Audit systems should
separate execution state, scoring state, and evidential support, then report
coverage and missingness beside every aggregate score.

This is a reliability problem, not a proposal to assign every failed audit the
worst possible score. A refusal may reflect judge policy, a timeout may reflect
infrastructure, and an abstention may be the correct response to insufficient
evidence. The requirement is narrower: preserve the reason, do not synthesize a
safety finding, and make the uncertainty visible to the reviewer.

## Audience

This pattern is for agent-eval maintainers, alignment-auditing researchers,
control-evaluation teams, and reviewers who use aggregate monitor or judge
scores to make deployment decisions. It responds directly to the failure mode
described in [Inspect Petri issue #113](https://github.com/meridianlabs-ai/inspect_petri/issues/113),
and complements current work on the [AuditBench tool-to-agent gap](https://alignment.anthropic.com/2026/auditbench/),
[ControlArena trajectory monitoring](https://control-arena.aisi.org.uk/), and
[NIST agentic evaluation probes](https://www.nist.gov/programs-projects/building-evaluation-probes-agentic-ai).

## Proposed Status Contract

Keep three questions separate:

```json
{
  "execution_status": "completed | failed",
  "scoring_status": "scored | refused | failed | not_scored | abstained",
  "score": "number | null",
  "failure_class": "string | null",
  "evidence_status": "available | missing"
}
```

Only `scored` records may contain a numeric score or enter the observed mean.
Every other scoring status must retain `score: null`, a specific failure class,
and `evidence_status: missing`. A numeric score makes evidence available; it
does not prove that the score or audit conclusion is correct. A failed target
execution must never be relabelled as a safely empty response.

## Six-Case Regression Matrix

| Case | Execution | Scoring | Aggregate treatment | Required visible result |
| --- | --- | --- | --- | --- |
| Benign result | completed | scored | Include score | Ordinary scored evidence |
| Concerning result | completed | scored | Include score | Ordinary scored evidence |
| Judge refusal | completed | refused | Exclude score | Refusal count and missing evidence |
| Judge timeout | completed | failed | Exclude score | Failure class and missing evidence |
| Target run failure | failed | not_scored | Exclude score | Execution failure, never a benign score |
| Auditor abstention | completed | abstained | Exclude score | Insufficient-evidence reason |

The executable fixture in
[`examples/failure-semantics.json`](../examples/failure-semantics.json) covers
all six cases. Run it with:

```sh
python3 -B examples/check_failure_semantics.py
```

## Metrics

Every batch summary should expose:

- attempted, scored, refused, failed, not-scored, and abstained counts,
  including explicit zero counts;
- scoring coverage: `scored / attempted`;
- the observed mean over scored cases, clearly labelled;
- best- and worst-case aggregate bounds over the declared score scale; and
- missingness by failure class, so reviewers can distinguish model behavior
  from evaluator or infrastructure failure.

The bounds are sensitivity analysis, not imputed findings. They show how much
the headline could move if missing cases were systematically benign or
concerning.

## Smallest External Contribution

Start with synthetic regression fixtures and explicit summary fields. Do not
change a framework's scoring policy until its maintainers choose the desired
semantics. The first useful upstream contribution is therefore a focused test
and reporting patch that makes silent missingness impossible, followed by a
small cross-framework comparison if maintainers find the pattern useful.

## Boundary

This note and its fixtures use only public sources and synthetic cases. They do
not contain private transcripts, benchmark solutions, model credentials, or
claims that any specific framework is unsafe overall.
