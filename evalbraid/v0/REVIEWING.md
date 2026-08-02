# Reviewing EvalBraid Evaluation Provenance Profile v0

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

EvalBraid can be used now for experimental pilots, integration checks, and
conformance work. Independent review strengthens the claims that can be made
about it; it is not permission to try the profile. Partial findings are useful,
and reproduction does not require endorsement of the profile or its
terminology.

## Review questions

1. Does the schema describe the stated structural boundary without altering
   stable EvidenceGate v1?
2. Do the semantic finding codes and JSON Pointer paths match the documented
   rules?
3. Does a passed verifier require both a null `failure_class` and a
   `not_applicable` first-failure status, with a valid open machine code for
   every non-passing status?
4. Does every failure class remain attempt-level and distinct from the human
   summary and causal attribution?
5. Do Python and Node produce the same canonical result for all 33 fixtures?
6. Can any malformed, ambiguous, or incomplete record pass unexpectedly?
7. Do the examples or terminology create privacy, integrity, fairness,
   attribution, or branding concerns?

## Environment setup

The recorded author environment used CPython 3.12.13 on macOS arm64 with
`jsonschema==4.26.0` and the exact hash-pinned
`evalbraid/v0/requirements.macos.lock`. It also used Node 24.14.0,
Ajv 8.20.0, and ajv-formats 3.0.1 from the exact npm lock.

The Python lock is intentionally labelled macOS. It is not Linux evidence.
Dependency acquisition may require network access; the validation programs
themselves deny or count network attempts.

Representative setup:

```sh
python3.12 -m venv .venv-profile
uv pip sync evalbraid/v0/requirements.macos.lock \
  --python .venv-profile/bin/python \
  --require-hashes --strict --no-sources

npm ci --prefix replication/node/evalbraid-v0 \
  --ignore-scripts --no-audit --no-fund
```

## One-command gate

After installing the locked dependencies:

```sh
.venv-profile/bin/python -B \
  tools/check_evalbraid_experimental.py --json
```

The gate checks the profile manifest, Python core corpus, Python regression
and adversarial tests, Node core and adversarial corpus, Node tests, all 33
cross-consumer projections, selected byte-identical outputs, zero validation
network attempts, and input immutability.

A passing local gate establishes only that those checks passed in the recorded
environment. It does not establish Linux portability, reviewer independence,
authentication, factual truth, safety, or production readiness.

## Submit a review receipt

Record:

- reviewer name or stable pseudonym and conflict statement;
- operating system, architecture, Python, Node, Ajv, and jsonschema versions;
- exact repository commit and artifact-manifest SHA-256;
- exact commands and exit codes;
- complete stdout and stderr SHA-256 values;
- fixture counts and any projection mismatches;
- every finding with severity, path or rule, evidence, and proposed
  disposition; and
- whether the review was technical reproduction, semantic review, privacy
  review, rights review, or another bounded contribution.

Do not include credentials, private evaluation records, raw trajectories,
personal data, vendor material, or confidential benchmark assets.
