# EvidenceGate Architecture And Stability Boundaries

EvidenceGate is deliberately split into one stable contract and adjacent
experiments. Sharing a repository does not make every experiment part of the
stable receipt schema.

## Stable Contract: Git-Change Receipt V1

The stable v1 contract has one subject type: `git_change`. It is defined by:

- the machine-readable
  [JSON Schema](../schemas/agent-run-receipt-v1.schema.json);
- the relational checks in `validate_v1_packet`;
- repository-state comparison in `verify_repository`;
- safe reviewer-facing Markdown rendering; and
- the portable [conformance corpus](../conformance/v1/README.md).

The JSON Schema covers structure. The validator adds relationships that are
awkward or impossible to express there: unique IDs, exact revision agreement,
claim-to-check references, passing evidence, path protection, and base/head
differences. Repository verification then compares a structurally valid
receipt with one local Git checkout.

Unknown v1 fields are rejected. Optional `extensions` may hold namespaced
metadata, but v1 deliberately ignores that content during validation,
verification, and rendering. Extension data cannot change a gate result.

## Experimental Contract: Failure Semantics

[`missing-evidence-is-not-safety.md`](missing-evidence-is-not-safety.md) and
its executable fixture are an experimental research slice. They test a useful
audit invariant: failed, refused, timed-out, and abstained evaluations must not
silently become evidence of safety.

This experiment is not an EvidenceGate v1 subject or predicate. Its statuses,
scores, and aggregate bounds do not become part of a Git-change receipt merely
because they live in this repository.

## Adjacent Proof Profiles

The stable v1 receipt can be carried by the experimental
[attestation profile](../attestation/v0/README.md). That profile binds the raw
receipt digest, base revision, head revision, repository subject, issuer claim,
and validity window inside an in-toto Statement. Its checker validates those
relationships and deliberately reports the statement as **UNAUTHENTICATED**.
Identity verification remains the job of a standard signed envelope and
verifier.

The [reviewer study](../study/v0/README.md) is another separate proof surface.
It measures decisions about synthetic Git-change scenarios; it does not add
fields or authority to the stable receipt.

## Not Yet Implemented

EvidenceGate does not currently define:

- a general agent-audit receipt;
- a hidden-state or interpretability evidence card;
- an authenticated envelope or authenticated reviewer identity;
- a signature, transparency log, or trusted timestamp; or
- a hosted policy or approval service.

Public work that applies the same evidence-hygiene principles should say it is
"informed by EvidenceGate" unless it implements and passes a separately
versioned predicate and conformance corpus.

## Evolution Rules

1. V1 bug fixes may reject inputs that were ambiguous, non-standard JSON, or
   capable of altering reviewer-facing Markdown structure.
2. New authoritative fields require a new schema version or predicate. They
   must not be smuggled through `extensions`.
3. Every schema change must update the JSON Schema, template, documentation,
   conformance fixtures, and runtime/schema alignment tests together.
4. Authentication must use an established envelope and verifier. EvidenceGate
   will not invent cryptography.
5. An experimental predicate cannot be described as stable until it has a
   threat model, fixtures, a conformance runner, and real authenticated use.

## Interoperability Direction

The experimental profile now defines an EvidenceGate predicate inside an
[in-toto Statement and authenticated envelope](https://github.com/in-toto/attestation).
Sigstore or a platform attestation service must still handle signer identity
and verification. Git commits remain the v1 subject; the envelope would
authenticate who or what issued the statement. The checked-in statements are
unsigned contract fixtures, not authenticated records.
