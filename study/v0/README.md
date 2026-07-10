# EvidenceGate Reviewer Study V0

This kit tests whether an EvidenceGate receipt changes review decisions compared
with the same transcript alone. It is ready to prepare packets and score real
responses. It contains **no reviewer results** and therefore supports no claim
that EvidenceGate improves accuracy, speed, or confidence calibration.

The twelve synthetic cases include six sound changes and six unsafe or
unsupported changes. The adverse cases cover stale evidence, scope drift,
unsupported claims, fabricated evidence, failed required checks, and
insufficient coverage. Arms A and B are complementary: each participant sees
every scenario once, half transcript-only and half receipt-assisted, while an
equal-sized opposite arm sees each scenario under the other condition.

First check the study machinery:

```sh
python3 -B tools/check_reviewer_study.py
```

Prepare one participant. Keep the coordinator key somewhere the participant
cannot access:

```sh
python3 -B tools/prepare_reviewer_study.py \
  --participant reviewer-001 \
  --arm A \
  --packet /tmp/reviewer-001-packet.json \
  --response-template /tmp/reviewer-001-response.json \
  --coordinator-key /tmp/coordinator/reviewer-001-key.json
```

After the participant completes every response, score one or more key/response
pairs:

```sh
python3 -B tools/score_reviewer_study.py \
  --pair /tmp/coordinator/reviewer-001-key.json /tmp/reviewer-001-response.json \
  --output /tmp/study-summary.json
```

The standard-library scorer reports descriptive condition outcomes and a
contrast. It deliberately does not calculate significance or declare uplift.
Complete and register the [protocol](protocol.md) before collecting data.

## Separation Rules

- Participants receive only the packet and response template.
- Coordinators retain keys separately and assign equal numbers to arms A and B.
- Do not replace missing reviewers with generated or idealized responses.
- Do not inspect accumulating condition results and stop when they look good.
- Publish anonymized responses, exclusions, analysis code, null results, adverse
  effects, and deviations together.
- Treat receipt-assisted acceptance of the fabricated-evidence case as a
  critical false-assurance signal, not an inconvenient outlier.
