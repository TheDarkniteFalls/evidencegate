# EvalBraid Evaluation Provenance Profile v0

```text
Maturity: Experimental v0
Validation: Author-tested on macOS against the published conformance corpus
Implementation diversity: Python and Node results agree
Linux portability: Not tested
Independent review: Requested — not yet completed
Production use: Not recommended
Authentication: Not provided
Stable EvidenceGate v1: Unchanged
```

Status token:
`experimental_author_tested_macos_linux_untested_review_requested`

This profile records evidence and judgment boundaries for one evaluation
attempt across trajectory and self-check, handoff and lifecycle, verifier
definition, executed verifier, policy, and adjudication layers.

It is an adjacent experimental contract. It does not add fields to, alter, or
interpret the stable EvidenceGate v1 Git-change receipt.

## Included surfaces

- Draft 2020-12 JSON Schema:
  `schemas/evalbraid-evaluation-provenance-v0.schema.json`
- three synthetic examples in `evalbraid/v0/examples/`;
- three positive and twenty-one single-mutation negative core fixtures in
  `evalbraid/v0/conformance/`;
- four targeted adversarial fixtures under
  `evalbraid/v0/conformance/adversarial/`;
- a Python structural and semantic validator;
- a separately written first-party Node consumer; and
- deterministic tests and a profile-specific reviewer gate.

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
