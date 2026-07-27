# Private Node consumer — EvalBraid Evaluation Provenance Profile v0

Status: experimental first-party implementation; independent review requested\
License: MIT; package publication disabled\
Stable EvidenceGate v1: unchanged\

This Node 24.14.0 consumer independently implements the candidate profile's
strict loading, Draft 2020-12 structural validation, semantic rules, stable
record-result contract, and conformance projection. It does not import or run
the Python validator, execute record content, fetch evidence, or authenticate a
record.

Dependencies are locked to Ajv 8.20.0 and ajv-formats 3.0.1. Environment
preparation is separate from validation:

```text
npm ci --offline --ignore-scripts --no-audit --no-fund
```

Set `EVALBRAID_NODE_ENV` to that installation root. Run with the exact Node
locked runtime used for author testing:

```text
node check-conformance.mjs --json
node test-consumer.mjs
node validate-record.mjs RECORD --json
```

Exit 0 means conformant or a complete aggregate pass, exit 1 means a checked
rejection/failure, and exit 2 means a load, schema-bootstrap, dependency, or
tool failure. Validation is read-only and offline. The consumer is first-party
implementation diversity, not independent validation.
