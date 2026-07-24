# EvidenceGate Release Checklist

Use this checklist for every tagged release. A local pass does not authorize a
push, merge, package upload, or publication.

## Contract

- [ ] The Git-change v1 JSON Schema, template, examples, runtime constants, and
  conformance manifest agree.
- [ ] The CLI result JSON Schema, runtime finding codes, integration guide, and
  conformance expectations agree.
- [ ] Every breaking contract change uses a new schema or predicate version.
- [ ] `extensions` remain non-authoritative and cannot change a gate result.
- [ ] `CHANGELOG.md` names user-visible, compatibility, and security changes.
- [ ] The v0.1.0 release notes match the final clean revision and package.

## Verification

- [ ] `python3 -B evidencegate.py --self-test`
- [ ] `python3 -B -m unittest discover -s tests -v`
- [ ] `python3 -B tools/check_conformance.py`
- [ ] JSON `validate` and `verify` results pass their schema and finding-code
  tests.
- [ ] `node replication/node/check-conformance.mjs`
- [ ] `python3 -B tools/check_attestation_conformance.py`
- [ ] `python3 -B tools/check_reviewer_study.py`
- [ ] `python3 -B examples/run-v1-reference.py`
- [ ] `python3 -B examples/check_failure_semantics.py`
- [ ] Package installation and the `evidencegate` console entry point pass in a
  clean virtual environment.
- [ ] The required GitHub Actions matrix passes on the release commit.
- [ ] `python3 -B tools/check_remarkable_candidate.py --report <path>` passes
  on the clean release commit and the report records that exact SHA.

## Human And Security Review

- [ ] A human reviews the complete diff and actual command output.
- [ ] Adversarial parser and renderer fixtures still fail safely.
- [ ] `SECURITY.md`, architecture boundaries, and trust claims remain accurate.
- [ ] Public wording follows the claim matrix and does not collapse
  authentication-ready into authenticated, first-party into independent, or a
  study protocol into a measured result.
- [ ] Repository history and the release diff contain no credentials, private
  logs, personal data, or private project paths.
- [ ] Third-party actions are pinned to verified full commit SHAs with explicit
  minimum token permissions.

## Publication

- [ ] `main` requires the complete quality workflow before merge.
- [ ] The release commit is clean, immutable, and identified by its full SHA.
- [ ] The version and tag match the changelog entry, and the release notes state
  whether the tag is signed.
- [ ] Release notes repeat the authentication and publication-authority boundary.
- [ ] Any "remarkable candidate" claim cites the exact clean revision whose
  aggregate gate passed.
- [ ] Package or artifact publication, if any, has separate explicit approval.
