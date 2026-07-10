# EvidenceGate Claim Matrix

Use the strongest sentence whose evidence column is currently satisfied.
Keep the qualifier in the sentence; it is part of the claim.

| Claim | Evidence required | Status |
| --- | --- | --- |
| "EvidenceGate is a hardened reference implementation for revision-bound agent-work receipts." | Strict parser, schema, relational and repository verification, safe rendering, adversarial fixtures, and cross-platform CI. | Earned on merged `main`; cite a release SHA or tag. |
| "EvidenceGate is a remarkable candidate: a complete, adversarially tested, cross-language, authentication-ready, empirically testable reference design." | All Phase 1 gates in the remarkable roadmap pass on one clean revision. | Earned only after the candidate branch passes and is merged. |
| "Two first-party implementations agree on the public v1 corpus." | Python and Node runners produce the same declared outcomes in CI. | Earned when the Node runner is in the required workflow. |
| "EvidenceGate is authentication-ready." | The public in-toto profile binds receipt bytes and Git subject; attack fixtures pass; signing is delegated to standard tooling. | Earned when the profile gates pass. This does **not** mean any receipt is authenticated. |
| "EvidenceGate provides a reproducible protocol for measuring reviewer effects." | Blinded packets, counterbalancing, response schema, scorer, adverse cases, and limitations are public and tested. | Earned when the study self-test passes. This does **not** mean uplift exists. |
| "EvidenceGate improves reviewer accuracy or speed." | Real reviewer responses analyzed under the published protocol support the precise effect claimed. | Unearned until data exists. |
| "EvidenceGate receipts are authenticated." | A named standard verifier validates a signed envelope, identity policy, subject, and validity window for the cited artifact. | Unearned for bare JSON receipts or unsigned statements. |
| "EvidenceGate is independently validated." | A named unaffiliated party publishes inspectable methods and results. | Unearned until that happens. |

## Recommended Public Description

> EvidenceGate is a hardened reference implementation for revision-bound
> receipts from human-reviewed agent work. Its remarkable-candidate package
> includes adversarial contract tests, a second-language consumer, an unsigned
> in-toto attestation profile ready for standard signing, and a reproducible
> reviewer-study kit. It does not claim that unsigned receipts are authentic or
> that reviewer uplift has been measured before real study data exists.

## Prohibited Shortcuts

- Do not turn "authentication-ready" into "authenticated."
- Do not describe first-party cross-language agreement as independent
  replication.
- Do not score generated, idealized, or fixture responses as reviewer results.
- Do not use stars, downloads, CI badges, or a passing receipt as evidence that
  the underlying claims are true.
- Do not call `main` or a release remarkable unless every cited gate passed on
  that exact revision.
