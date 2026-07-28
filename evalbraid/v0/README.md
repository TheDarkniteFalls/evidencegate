# EvalBraid Evaluation Provenance Profile v0

```text
Maturity: Experimental v0
Validation: Author-tested on macOS against the published conformance corpus
Implementation diversity: Python and Node results agree
Intended use: Experimental pilots, integration tests, conformance work, and review
Linux portability: Not tested
Independent review: Requested — not yet completed
Production reliance: Not recommended
Authentication: Not provided
Stable EvidenceGate v1: Unchanged
```

Status token:
`experimental_author_tested_macos_linux_untested_review_requested`

This profile records evidence and judgment boundaries for one evaluation
attempt across trajectory and self-check, handoff and lifecycle, verifier
definition, executed verifier, policy, and adjudication layers.

It is usable now as an experimental public asset. Evaluation teams can use it
to draft attempt-bounded provenance records, test producers and consumers
against one versioned contract, reproduce the conformance corpus, and report
gaps before adopting a stable or production dependency.

It is an adjacent experimental contract. It does not add fields to, alter, or
interpret the stable EvidenceGate v1 Git-change receipt.

## Included surfaces

- Draft 2020-12 JSON Schema:
  `schemas/evalbraid-evaluation-provenance-v0.schema.json`
- three synthetic examples in `evalbraid/v0/examples/`;
- three positive and twenty-five single-mutation negative core fixtures in
  `evalbraid/v0/conformance/`;
- four targeted adversarial fixtures under
  `evalbraid/v0/conformance/adversarial/`;
- a Python structural and semantic validator;
- a separately written first-party Node consumer; and
- deterministic tests and a profile-specific reviewer gate.

## Verifier outcome and reason boundary

`verifier_result.execution_status` is the closed outcome vocabulary. The
required `verifier_result.failure_class` is `null` when that status is
`passed`; every other status requires a lowercase open-vocabulary machine code
such as `output_length_exceeded` or `verifier_result_not_observed`.

The machine code belongs to this one attempt. It is separate from the bounded
human explanation in `first_failure_or_threshold` and from
`evaluation_judgment.causal_attribution`, which records the assessed cause.
Producers must not replace attempt records with batch counts, infer a missing
class from prose or attribution, or resurrect a removed value during import or
editing. A deliberate later change belongs in the explicit adjudication
record.

## Try it

After installing the locked dependencies described in `REVIEWING.md`, validate
one synthetic example from the repository root:

```sh
.venv-profile/bin/python -B tools/evalbraid_contract.py \
  evalbraid/v0/examples/valid-static-explained.json --json
```

The result should report `"valid":true`. This proves only that the supplied
record passed the profile's structural and semantic checks. Use the
one-command gate in `REVIEWING.md` to reproduce the complete author-tested
conformance package.

The semantic validator emits the unchanged
`evalbraid_evaluation_provenance_result_v0` contract:

```text
contract
valid
profile
record_sha256
schema_sha256
findings[] { code, path, message }
```

Exit `0` means that the supplied record passed structural and semantic checks.
Exit `1` means it was rejected. Exit `2` means a load, dependency, schema, or
tool failure prevented a decision. These meanings do not authenticate the
record or establish that its claims are factually true.

## Scope limits

The profile does not fetch evidence, execute a verifier named by a record,
recompute external artifact digests, determine factual truth, prove evidence
independence, infer malicious intent, approve a benchmark result, or authorize
publication. The Python and Node implementations are maintained by the same
project and do not constitute independent review.

See `REVIEWING.md` for reproduction instructions, `THREAT_MODEL.md` for the
security boundary, and `ATTRIBUTION.md` for licensing and contextual sources.
