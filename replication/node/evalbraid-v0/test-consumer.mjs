#!/usr/bin/env node
// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { projection, runConformance } from "./check-conformance.mjs";
import { runFormatProbes } from "./schema-validator.mjs";
import { strictParse, StrictJsonError } from "./strict-json.mjs";
import { validateRecord } from "./validate-record.mjs";

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(MODULE_DIR, "../../..");
const POSITIVE = path.join(ROOT, "evalbraid", "v0", "conformance", "positive", "valid-static-explained.json");
const MULTI = path.join(ROOT, "evalbraid", "v0", "conformance", "adversarial", "invalid-multiple-semantic-findings.json");

function expectStrictCode(text, code) {
  assert.throws(
    () => strictParse(text),
    (error) => error instanceof StrictJsonError && error.code === code,
  );
}

function testStrictLoading() {
  expectStrictCode('{"outer":{"x":1,"x":2}}', "profile_load_duplicate_key");
  expectStrictCode('{"text":"\\ud800"}', "profile_load_invalid_unicode");
  expectStrictCode('{"number":1e999}', "profile_load_number_invalid");
  expectStrictCode("[]", "profile_load_top_level_invalid");
  expectStrictCode(`${"[".repeat(257)}0${"]".repeat(257)}`, "profile_load_nesting_too_deep");
}

function testConformanceAndDeterminism() {
  const probes = runFormatProbes().probes;
  assert.deepEqual(probes, { uuid: true, date_time: true, uri: true });
  const result = runConformance();
  assert.equal(result.valid, true);
  assert.deepEqual(result.counts.core, { total: 28, positive: 3, negative: 25, passed: 28 });
  assert.deepEqual(result.counts.overlay, { total: 4, passed: 4 });
  assert.equal(result.network_attempts, 0);
  for (const fixture of [POSITIVE, MULTI]) {
    const first = validateRecord(fixture);
    const second = validateRecord(fixture);
    assert.equal(JSON.stringify(first.result), JSON.stringify(second.result));
    assert.deepEqual(projection(first), projection(second));
  }
}

function testObjectOrderMetamorphism() {
  const original = JSON.parse(fs.readFileSync(POSITIVE, "utf8"));
  const reordered = Object.fromEntries(Object.entries(original).reverse());
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "evalbraid-node-test-"));
  const candidate = path.join(directory, "reordered.json");
  try {
    fs.writeFileSync(candidate, `${JSON.stringify(reordered, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
    const baseline = validateRecord(POSITIVE);
    const changed = validateRecord(candidate);
    assert.equal(changed.stage, "pass");
    assert.notEqual(changed.result.record_sha256, baseline.result.record_sha256);
    assert.equal(changed.result.valid, baseline.result.valid);
    assert.equal(changed.result.schema_sha256, baseline.result.schema_sha256);
    assert.deepEqual(changed.result.findings, baseline.result.findings);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

function testLegacyProfileAliasRejected() {
  const original = JSON.parse(fs.readFileSync(POSITIVE, "utf8"));
  const legacy = { ...original, profile: "evidencegate_evaluation_provenance_v0" };
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "evalbraid-legacy-alias-"));
  const candidate = path.join(directory, "legacy-profile.json");
  try {
    fs.writeFileSync(candidate, `${JSON.stringify(legacy, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
    const outcome = validateRecord(candidate);
    assert.equal(outcome.stage, "schema_error");
    assert.equal(outcome.exitCode, 1);
    assert.equal(outcome.result.findings.some((item) =>
      item.code === "profile_schema_invalid" && item.path === "/profile"), true);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

function testFailureClassBoundary() {
  const original = JSON.parse(fs.readFileSync(POSITIVE, "utf8"));
  assert.equal(original.verifier_result.failure_class, "output_length_exceeded");
  assert.equal(original.evaluation_judgment.causal_attribution, "agent");
  const passed = structuredClone(original);
  Object.assign(passed.verifier_result, {
    execution_status: "passed",
    failure_class: null,
    exit_status: { status: "observed", code: 0 },
    reward: { status: "observed", value: 1 },
    first_failure_or_threshold: {
      status: "not_applicable",
      reason: "Verifier passed; no failure or threshold breach occurred.",
    },
  });
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "evalbraid-passed-"));
  const candidate = path.join(directory, "passed.json");
  try {
    fs.writeFileSync(candidate, `${JSON.stringify(passed, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
    const outcome = validateRecord(candidate);
    assert.equal(outcome.stage, "pass");
    assert.equal(outcome.exitCode, 0);
    assert.equal(outcome.result.valid, true);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

function testCapabilitySurface() {
  const forbidden = /(?:from\s+|import\s*)["'](?:node:)?(?:child_process|http|https|net|tls|dgram)["']|\bimport\s*\(/;
  const sources = fs.readdirSync(MODULE_DIR)
    .filter((name) => name.endsWith(".mjs") && name !== "test-consumer.mjs");
  for (const name of sources) {
    const text = fs.readFileSync(path.join(MODULE_DIR, name), "utf8");
    assert.equal(forbidden.test(text), false, `${name} exposes a forbidden network or subprocess capability`);
  }
  const packageJson = JSON.parse(fs.readFileSync(path.join(MODULE_DIR, "package.json"), "utf8"));
  assert.deepEqual(packageJson.dependencies, { ajv: "8.20.0", "ajv-formats": "3.0.1" });
}

function main() {
  testStrictLoading();
  testConformanceAndDeterminism();
  testObjectOrderMetamorphism();
  testLegacyProfileAliasRejected();
  testFailureClassBoundary();
  testCapabilitySurface();
  process.stdout.write("PASS node consumer tests: strict loading, 32 cases, determinism, metamorphism, capability surface\n");
}

try {
  main();
} catch (error) {
  process.stderr.write(`FAIL node consumer tests: ${error.stack || error.message}\n`);
  process.exitCode = 1;
}
