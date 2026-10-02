# Node V1 Conformance Consumer

Run this Node program to check the same public test cases using a separately
written implementation. It needs no dependencies and reads the EvidenceGate
v1 conformance manifest—the list of fixtures and their expected outcomes. It implements strict JSON parsing,
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

Use this program to compare fixture outcomes. It does not replace the main
command-line tool. Repository
verification remains implemented by the Python reference tool.
