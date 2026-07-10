# EvidenceGate V1 Conformance Corpus

This directory is the portable behavior contract for EvidenceGate Git-change
receipts. Each case is synthetic. `manifest.json` declares whether a consumer
must accept the receipt, reject it during JSON loading, or reject it during v1
validation.

Run the reference checker with:

```sh
python3 -B tools/check_conformance.py
```

The corpus tests security-relevant interoperability boundaries that a JSON
Schema alone cannot express reliably across implementations, including
duplicate object keys, revision relationships, claim-to-check relationships,
and safe reviewer-facing rendering.

The schema in
[`schemas/agent-run-receipt-v1.schema.json`](../../schemas/agent-run-receipt-v1.schema.json)
is the machine-readable structural contract. The conformance corpus and CLI
define the additional relational and rendering behavior.
