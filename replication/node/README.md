# Node V1 Conformance Consumer

This dependency-free Node program is a separately written consumer of the
public EvidenceGate v1 conformance manifest. It implements strict JSON parsing,
the relationships exercised by the corpus, and the renderer attack contract
without importing or executing the Python implementation.

```sh
node replication/node/check-conformance.mjs
```

Agreement between the Python and Node programs is **first-party cross-language
replication**. It is useful evidence that the public corpus is implementable,
but it is not independent validation: both live in the same repository and are
maintained by the same project. A third party can use either runner's output
shape and the language-neutral manifest to publish an independent result.

The Node consumer is a conformance oracle, not a replacement CLI. Repository
verification remains implemented by the Python reference tool.
