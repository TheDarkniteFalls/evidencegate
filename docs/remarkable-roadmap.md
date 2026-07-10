# The Path From Useful To Remarkable

"Remarkable" is not a release label. EvidenceGate earns it only if outsiders
can reproduce the contract, attack its assumptions, and measure whether it
improves review decisions without creating false assurance.

## Claim Ladder

EvidenceGate may make only the strongest claim whose exit criteria are met:

1. **Useful pattern:** a receipt makes final-state evidence easier to inspect.
2. **Hardened reference:** adversarial inputs cannot silently change the
   contract or reviewer-facing structure.
3. **Interoperable predicate:** an independent implementation reaches the same
   conformance results.
4. **Authenticated record:** an established envelope verifies issuer identity
   and receipt integrity.
5. **Measured review aid:** controlled evaluation shows where receipts improve
   reviewer accuracy or speed and where they do not.

The current project is pursuing level 2. It must not claim levels 3-5 early.

## Stage 1: Harden The Reference Contract

Exit criteria:

- reject duplicate keys, non-standard JSON constants, oversized packets, and
  undeclared authoritative fields;
- render supplied text without permitting Markdown or HTML structure injection;
- handle zero-scored audit batches without crashing;
- publish a strict v1 JSON Schema and portable positive/negative corpus; and
- keep runtime constants and schema enums locked by tests.

This stage is implemented locally when the full quality stack passes.

## Stage 2: Make V1 A Reproducible Release

Exit criteria:

- CI passes on the declared minimum, intermediate, and current Python versions
  across Linux, macOS, and Windows;
- workflow permissions are read-only and third-party actions are commit-pinned;
- `main` requires the quality workflow before merge;
- the [release checklist](release-checklist.md) covers schema, corpus, CLI,
  security, and public-safety review; and
- a signed version tag identifies the first stable contract.

Repository settings and the version tag require an explicit publication
decision; source changes alone cannot complete this stage.

## Stage 3: Authenticate Without Inventing Cryptography

Start with a design and threat model, not implementation. Define an EvidenceGate
predicate carried by an in-toto statement and DSSE/Sigstore-compatible envelope.
Record evidence descriptors and digests for command output, runner context, and
review decisions. Keep local unsigned receipts supported and visibly distinct.

Exit criteria:

- a documented trust model identifies issuer, verifier, compromised-runner, and
  replay threats;
- tampered receipts, wrong subjects, wrong signers, and expired policy fail in
  public fixtures;
- GitHub or Sigstore tooling verifies the envelope; and
- no custom signing or key-management code is introduced.

## Stage 4: Define Audit Predicates Separately

Create experimental predicates only when a real use case requires them. An
agent-audit predicate may preserve execution, scoring, and evidence status. A
hidden-state evidence card may preserve hypotheses, corroboration, and
disconfirmation. Neither should inherit Git-specific fields by accident.

Each predicate needs its own schema version, threat model, corpus, and maturity
label. Cross-predicate concepts should move into a core envelope only after two
implementations demonstrate the abstraction.

## Stage 5: Measure Reviewer Uplift And False Assurance

Pre-register a comparison of transcript-only review against receipt-assisted
review. Set sample size by power analysis and include ordinary, stale-evidence,
scope-drift, unsupported-claim, fabricated-receipt, and incomplete-evidence
cases.

Measure:

- acceptance of unsafe or unsupported changes;
- rejection of sound changes;
- time to a justified decision;
- detection of stale evidence and scope drift;
- confidence calibration; and
- cases where a polished receipt creates more false assurance than a transcript.

Publish the fixtures, anonymized decisions, analysis code, negative results, and
limitations. Stop or narrow the product if receipts do not improve decisions.

## Stage 6: External Replication

The final credibility step is outside this repository:

- an independent consumer passes the conformance corpus;
- an external reviewer attacks the threat model and renderer/parser boundary;
- at least one real project uses receipts without relying on private context;
  and
- disagreements become public fixtures or specification changes.

Only after these stages would "remarkable foundation" be an evidence-backed
description rather than marketing.
