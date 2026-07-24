# Changelog

All notable changes to the EvidenceGate receipt contract and reference
implementation will be documented here.

## 0.1.0 - 2026-07-24

[Release notes](docs/v0.1.0-release-notes.md)

### Added

- A strict machine-readable JSON Schema for Git-change receipt v1.
- A portable positive and negative v1 conformance corpus with a standard-library
  runner.
- Python package metadata and an `evidencegate` console entry point for the
  declared Python 3.10+ runtime.
- Optional, pinned JSON Schema meta-validation tooling for the test environment;
  the CLI keeps a zero-dependency runtime.
- Architecture boundaries separating stable Git receipts from experimental
  audit-failure research.
- A staged, falsifiable roadmap for interoperability, authentication, measured
  reviewer uplift, and external replication.
- An unsigned in-toto-compatible attestation profile with strict subject,
  issuer-policy, receipt-digest, validity-window, and adversarial fixture checks.
- A blinded, counterbalanced twelve-case reviewer-study kit with response
  preparation, descriptive scoring, false-assurance cases, and a preregistration
  template.
- A separately written, dependency-free Node conformance consumer for
  first-party cross-language contract evidence.
- One aggregate remarkable-candidate gate and machine-readable evidence report.
- A versioned JSON result contract for `validate` and `verify`, stable finding
  codes, a result JSON Schema, and a pinned consumer CI recipe.

### Changed

- V1 now rejects undeclared fields. Non-authoritative metadata may be placed in
  the optional `extensions` object, which cannot affect validation or
  verification.
- Reviewer-facing Markdown now neutralizes supplied Markdown and HTML structure.
- The reference run uses the active Python interpreter for cross-platform CI.
- Read-only Git subprocesses disable filesystem monitors and pagers and fail
  closed after a bounded timeout.
- The remarkable roadmap now separates maintainer-controlled candidate proof
  from authenticated use, measured reviewer effects, and independent replication.

### Fixed

- Reject duplicate JSON object keys and non-standard constants such as `NaN`.
- Reject receipt files larger than the documented one-megabyte input limit.
- Report an unavailable observed mean instead of crashing when no audit case is
  scored.

### Security

- Rendering a valid but adversarial receipt can no longer inject a forged review
  heading or raw HTML into the generated Markdown.
