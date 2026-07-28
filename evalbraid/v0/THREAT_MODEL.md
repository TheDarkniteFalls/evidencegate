# EvalBraid Evaluation Provenance Profile v0 Threat Model

## Protected assets

- the exact bytes and identity of the record, schema, fixtures, and manifests;
- deterministic structural and semantic findings;
- separation between evidence, interpretation, adjudication, and authority;
- the stable EvidenceGate v1 contract; and
- reviewer privacy and the absence of private source material.

## In-scope inputs and actors

Records, fixtures, manifests, and reviewer-supplied paths are untrusted.
Producers may be mistaken, incomplete, compromised, or adversarial. Reviewers
and maintainers are trusted only for the explicit decisions they record; their
identity is not authenticated by this profile.

## Addressed threats

- duplicate JSON keys, invalid Unicode, non-standard constants, and malformed
  JSON;
- unknown schema fields and invalid UUID, date-time, or URI values;
- missing, duplicate, unresolved, orphaned, or layer-incompatible evidence
  references;
- inconsistent verifier digests, lifecycle links, time order, adjudication
  triggers, retained or revised pointers, or proven-fact evidence;
- omitted or malformed attempt-level failure classes, including non-null
  classes on passing outcomes and null classes on non-passing outcomes;
- self-checks mislabelled as independent;
- redistribution claims stronger than the referenced sources permit;
- non-deterministic or cross-consumer result drift; and
- validation code attempting network access.

## Not addressed

The profile does not authenticate an issuer or reviewer; fetch evidence;
verify that referenced URIs or digests correspond to truthful evidence;
execute a verifier; establish benchmark fairness; prevent a producer from
lying or choosing a misleading but syntactically valid open failure class;
protect a host from arbitrary third-party tooling; or prove that an
evaluation conclusion is correct. Linux portability has not been tested.

## Trust-preserving response

Parsing, dependency, schema-bootstrap, or tool failures return an indeterminate
tool error rather than a passing result. Semantic failures use stable finding
codes and JSON Pointer paths. A local pass remains environment-bounded and
does not grant publication or production authority.
