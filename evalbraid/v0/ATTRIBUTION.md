# Licensing and Attribution

## Project material

The schema, validators, synthetic fixtures, tests, manifests, and profile
documentation are project-authored, AI-assisted material intended for
distribution under the repository's MIT License. Source files that support
comments carry `SPDX-License-Identifier: MIT`. JSON, lock, and Markdown files
are covered by the repository license and this file map rather than inline
comments.

No private motivating record, vendor archive, benchmark task, trajectory, log,
screenshot, manuscript, personal data, credential, or third-party source code
is included.

## Direct dependencies

No dependency bytes, wheels, source distributions, installed packages,
virtual environments, `node_modules`, caches, or container layers are included
in this source-only profile tree. The lock and package metadata identify what
the recorded author-validation environments used; installing them is a
separate dependency distribution event governed by each package's own terms.

### Python environment

The macOS author-validation lock resolves `jsonschema[format-nongpl]==4.26.0`
to the following exact inventory:

| Distribution | Version | Relationship | Recorded license conclusion |
| --- | --- | --- | --- |
| `jsonschema` | `4.26.0` | Direct | MIT |
| `fqdn` | `1.5.1` | `format-nongpl` | MPL-2.0 |
| `idna` | `3.18` | `format-nongpl` | BSD-3-Clause |
| `isoduration` | `20.11.0` | `format-nongpl` | ISC |
| `jsonpointer` | `3.1.1` | `format-nongpl` | BSD-3-Clause |
| `rfc3339-validator` | `0.1.4` | `format-nongpl` | MIT |
| `rfc3986-validator` | `0.1.1` | `format-nongpl` | MIT |
| `rfc3987-syntax` | `1.1.0` | `format-nongpl` | MIT; legacy Apache classifier discrepancy requires recheck before dependency redistribution |
| `uri-template` | `1.3.0` | `format-nongpl` | MIT |
| `webcolors` | `25.10.0` | `format-nongpl` | BSD-3-Clause |
| `arrow` | `1.4.0` | Transitive | Apache-2.0 |
| `attrs` | `26.1.0` | Transitive | MIT |
| `jsonschema-specifications` | `2025.9.1` | Transitive | MIT |
| `lark` | `1.3.1` | Transitive | MIT |
| `python-dateutil` | `2.9.0.post0` | Transitive | Apache-2.0 OR BSD-3-Clause |
| `referencing` | `0.37.0` | Transitive | MIT |
| `rpds-py` | `2026.6.3` | Transitive | MIT |
| `six` | `1.17.0` | Transitive | MIT |
| `typing-extensions` | `4.16.0` | Transitive | PSF-2.0 |
| `tzdata` | `2026.3` | Transitive | Apache-2.0 |

The Python conclusions therefore include MIT, BSD-3-Clause, Apache-2.0, ISC,
MPL-2.0, PSF-2.0, and the recorded dual Apache-2.0-or-BSD-3-Clause treatment.

### Node environment

The first-party Node consumer uses Ajv 8.20.0 and ajv-formats 3.0.1 directly,
with fast-deep-equal 3.1.3, fast-uri 3.1.2, json-schema-traverse 1.0.0, and
require-from-string 2.0.2 transitively. Ajv, ajv-formats, fast-deep-equal,
json-schema-traverse, and require-from-string are recorded as MIT;
fast-uri is BSD-3-Clause.

An installer or binary distributor must reproduce the notices required by the
dependency bytes it actually redistributes. The project MIT License does not
relicense third-party dependencies. Exact local evidence remains in the frozen
D1 Python and D1.1 Node dependency records and must be rechecked before any
release or dependency-byte distribution.

## Contextual sources

The profile was informed by JSON Schema Draft 2020-12, general provenance and
evaluation-governance literature, and public evaluation-system documentation.
Those sources provide context; they do not define, certify, endorse, or sponsor
this profile. No specification, paper, documentation example, figure, table,
task, or source code is copied into the profile.

Specific current-source and legal claims should be rechecked before a release.
