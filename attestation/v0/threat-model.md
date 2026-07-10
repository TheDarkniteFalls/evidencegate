# Attestation Profile V0 Threat Model

## Assets And Trust Decision

The asset is a review decision about one Git change. A verifier wants to know
whether a specific issuer authenticated a short-lived statement that binds the
expected repository and head commit to the exact bytes of a valid EvidenceGate
v1 receipt.

The local profile checker is trusted only for parsing, relationship checks,
digest comparison, and time policy. A standard envelope verifier is trusted for
signature, certificate, identity, transparency-log, and trusted-time policy.
The producer, receipt, statement, repository checkout, and claimed issuer text
are untrusted inputs until those checks succeed.

## Covered By This Repository

| Threat | Control |
| --- | --- |
| Receipt bytes changed after statement creation | Raw receipt SHA-256 mismatch fails. |
| Statement points at the wrong commit | Statement subject and predicate head must equal the receipt head. |
| Statement points at the wrong repository | Caller-supplied expected subject must match exactly. |
| Attacker chooses their own issuer text | Caller-supplied expected issuer must match exactly. The text remains unauthenticated without an envelope. |
| Replay of an old otherwise-consistent statement | UTC validity window is mandatory, bounded to 24 hours, and checked against policy time. |
| Extra fields smuggle authority | Unknown fields are rejected at every profile level. |
| Malformed or ambiguous JSON changes interpretation | The reference strict loader rejects duplicate keys, non-standard constants, invalid UTF-8, excessive size, and unsafe nesting. |

## Requires A Standard Authenticated Envelope

The repository deliberately does not implement signature verification, key
management, identity federation, certificate-chain validation, transparency
log verification, revocation, or trusted timestamps. Those are not small JSON
validation problems and custom implementations would weaken this project.
The in-toto specification recommends
[DSSE v1.0 envelopes](https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md);
platform attestation services may apply their own compatible envelope and
identity policy.

Before calling a record authenticated, a deployment must use a named standard
verifier and pin policy for:

- the expected workflow or workload identity;
- the expected repository and Git revision;
- certificate issuer and validity;
- transparency-log inclusion where applicable;
- envelope payload type and the exact statement bytes; and
- the local profile checks in this repository.

## Residual Threats

An authenticated issuer can still lie, run inadequate checks, sign a receipt
for a compromised runner, or approve unsafe work. A hash proves byte identity,
not truth. Repository verification can detect state mismatch in a supplied
checkout, but neither it nor a signature proves semantic correctness.

## Attack Fixtures

The public corpus covers the valid unsigned contract, tampered receipt bytes,
wrong Git subject, wrong claimed issuer, and expiry. Wrong-signer and signature
corruption fixtures belong to the selected external verifier's own conformance
suite; this project will not simulate cryptographic assurance.
