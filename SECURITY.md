# Security

EvidenceGate processes receipts that may be produced by an agent or another
untrusted source. Parser ambiguity, reviewer-facing rendering injection, Git
state confusion, and false assurance are security-relevant defects.

## Reporting

Use GitHub private vulnerability reporting when it is available for this
repository. Otherwise open a minimal public issue that describes the affected
operation and impact without including exploit payloads, private receipts,
credentials, or personal data.

Use only synthetic packets in public reports. Do not include private logs,
connector exports, local paths, repository secrets, or real reviewer identity
data.

## Supported Surface

Security fixes target the current `main` branch and the v1 Git-change receipt
contract. Legacy receipts are structural-only and are not eligible for
repository verification.

The trust boundary is documented in
[`docs/architecture.md`](docs/architecture.md). EvidenceGate does not currently
authenticate receipts, evidence, command output, or reviewer identities. Report
any output or documentation that implies otherwise.

The experimental attestation profile validates an unsigned in-toto Statement's
structure, digest, subject, issuer-policy text, and validity window. It does not
verify a signature or identity and prints `UNAUTHENTICATED` on its only passing
contract path. Treat any bypass of that label, acceptance of an attack fixture,
or implication that digest agreement authenticates an issuer as a
security-relevant defect.
