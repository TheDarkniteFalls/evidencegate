# EvidenceGate Attestation Profile V0

This experimental profile places an EvidenceGate predicate in an in-toto
Statement. It binds the raw SHA-256 digest of one v1 receipt to the receipt's
base and head revisions, one expected Git repository subject, one expected
issuer claim, and a validity window of at most 24 hours.

The checked-in statements are intentionally unsigned. A passing local check
prints `UNAUTHENTICATED` because digest binding is not signer authentication.
Production use must wrap the statement with an established Sigstore, DSSE, or
platform attestation mechanism and apply verifier policy to the envelope before
trusting the claimed issuer.

Run the attack corpus:

```sh
python3 -B tools/check_attestation_conformance.py
```

Create a fresh unsigned statement from a valid receipt. The generator derives
the base/head revisions and raw receipt digest; the caller supplies the expected
repository subject, claimed issuer, and short validity policy:

```sh
python3 -B tools/create_attestation_statement.py \
  conformance/v1/valid-minimal.json \
  --subject git+https://github.com/TheDarkniteFalls/evidencegate \
  --claimed-issuer https://github.com/TheDarkniteFalls/evidencegate/.github/workflows/checks.yml@refs/heads/main \
  --valid-for-minutes 60 \
  --output /tmp/evidencegate-statement.json
```

The result is still unsigned and unauthenticated. Its Statement structure
follows the current
[in-toto v1 Statement layer](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md);
`gitCommit` is a predefined DigestSet algorithm. A deployment must choose and
verify a standard envelope.

Check the valid fixture directly at its deterministic policy time:

```sh
python3 -B tools/attestation_profile.py \
  attestation/v0/valid-unsigned.json \
  conformance/v1/valid-minimal.json \
  --expected-subject git+https://github.com/TheDarkniteFalls/evidencegate \
  --expected-issuer https://github.com/TheDarkniteFalls/evidencegate/.github/workflows/checks.yml@refs/heads/main \
  --at-time 2030-01-01T12:00:00Z
```

The profile checker proves only that the supplied statement and raw receipt
bytes agree with explicit local policy. See the [threat model](threat-model.md)
and [claim matrix](../../docs/marketing-claims.md).
