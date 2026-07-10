# The Shortest Path To Remarkable

EvidenceGate does not need adoption, sponsorship, or praise to become a
remarkable reference implementation. It does need to finish every proof its
maintainers control and make the proofs that require other people unusually
cheap to run.

This roadmap has two phases. Phase 1 is entirely maintainer-controlled. Phase 2
is evidence that only real use can create; the project supplies the protocol
and tooling but never invents the result.

## Phase 1: Complete The Reference Implementation

The repository earns **remarkable candidate** when all of these are true:

- the Git-change receipt has a strict schema, relational validator, safe
  renderer, repository verifier, adversarial corpus, and cross-platform CI;
- a separately written consumer in another language reaches the same public
  conformance outcomes;
- an in-toto-compatible attestation profile binds a receipt digest to its Git
  subject, documents the trust model, and rejects tampering, subject mismatch,
  and expiry without implementing custom cryptography;
- a blinded, counterbalanced reviewer-study kit can produce packets and score
  real decisions without silently substituting synthetic answers; and
- release evidence, claim boundaries, limitations, and exact reproduction
  commands are public and checked.

These are engineering and documentation tasks. We can complete them ourselves.
The phrase **remarkable candidate** means the design and proof package are
unusually complete for a small reference project. It does not mean the project
has been independently validated or shown to improve reviewer decisions.

## Phase 2: Accumulate Real-World Evidence

The repository earns stronger claims only from evidence that actually exists:

- **authenticated record** after a standard Sigstore or platform verifier
  authenticates a signed envelope produced by a real trusted workflow;
- **measured review aid** after real reviewers complete the published study and
  the analysis shows where receipts help, hurt, or have no effect; and
- **independently replicated** after an unaffiliated implementation or reviewer
  publishes results that can be inspected.

The project does not wait for Phase 2 to be useful or publishable. It makes
Phase 2 turnkey, labels it accurately, and treats every result—including a
negative one—as evidence rather than a marketing inconvenience.

## Stop Conditions

Narrow or change the project if any of these occur:

- the second implementation exposes an ambiguous contract the specification
  cannot resolve;
- the attestation profile encourages callers to confuse digest binding with
  identity authentication;
- the study shows more unsafe acceptance or worse confidence calibration with
  receipts; or
- maintenance cost grows faster than the review problem being solved.

## Publication Rule

Marketing copy must use the [claim matrix](marketing-claims.md). A checked box,
passing demo, or polished receipt never stands in for an external result.
