# Reviewer Study V0 Protocol And Preregistration Template

Complete every bracketed field, freeze the document, and record its digest
before recruitment. This template is a study design, not ethical approval or a
substitute for statistical review.

## Research Question

Does adding an EvidenceGate receipt and its deterministic validation/readiness
report to a fixed review transcript change a reviewer's ability to accept sound
changes and reject unsafe or unsupported changes?

Primary endpoint: unsafe acceptance rate. The directional hypothesis is that
receipt assistance lowers it. A rise—especially on fabricated evidence—is a
material adverse result.

Secondary endpoints are overall decision accuracy, sound-change rejection,
expected-reason detection, decision time, and Brier score for the supplied
probability of acceptance.

## Design

- Within-reviewer, counterbalanced comparison across twelve fixed synthetic
  scenarios.
- Each reviewer sees each scenario once: six transcript-only and six
  receipt-assisted.
- Arm B reverses every condition assignment in Arm A. Recruit equal numbers in
  each arm and assign arms before packet creation.
- Case IDs and presentation order are deterministically blinded per participant.
- Participants must not inspect this repository, scenario source, or coordinator
  keys until their responses are final.

This design estimates an effect across the published scenario set. It is not a
prevalence estimate for all software review and does not eliminate learning,
scenario, or reviewer-expertise effects.

## Population And Sample Size

- Target population: [define reviewer experience and domain].
- Inclusion criteria: [define before recruitment].
- Exclusion criteria: incomplete packet, source/key access, or [predeclare].
- Recruitment channel and compensation: [record].
- Target completed sample: [even number].
- Power or precision analysis: [attach assumptions, method, code, effect size,
  clustering treatment, and result].

Do not choose the sample size from accumulating EvidenceGate results. If the
study is too small for a defensible effect estimate, label it a usability pilot
and publish only descriptive results.

## Procedure

1. Record consent and a pseudonymous participant ID outside the response file.
2. Assign arms A/B in equal blocks using [method].
3. Generate and deliver the packet and response template.
4. Instruct the reviewer to decide independently and use only supplied material.
5. Record decision, at least one reason code, probability of acceptance from 0
   to 1, and elapsed seconds for every case.
6. Freeze returned responses before joining them with coordinator keys.
7. Hash and archive protocol, packets, keys, responses, exclusions, and code.

## Analysis

Use `score_reviewer_study.py` for the public descriptive table. Before data
collection, specify the confirmatory model for the primary endpoint, including
participant and scenario clustering, treatment of experience covariates,
missing data, multiplicity, confidence interval, and decision threshold:

[pre-register model and reviewed analysis code here]

Report per-scenario results alongside pooled results. A favorable pooled result
must not hide worse performance on fabricated evidence, scope drift, or another
named safety category.

## Privacy And Publication

Collect no names, emails, employer data, private repository content, or raw
screen recordings in the public response files. Publish pseudonymous decisions
only with consent and applicable review. State recruitment limits, exclusions,
protocol deviations, conflicts, null findings, and adverse findings.

## Registration Record

- Frozen protocol location: [URL or archive]
- SHA-256: [digest]
- Timestamp: [trusted timestamp]
- Study coordinator: [role or pseudonym]
- Independent statistical review: [name/role or explicitly none]
