#!/usr/bin/env node
// SPDX-License-Identifier: MIT
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { EXPECTED_SCHEMA_SHA256, loadSchema } from "./schema-validator.mjs";
import { loadObjectFile, sha256Bytes } from "./strict-json.mjs";
import { validateRecord } from "./validate-record.mjs";

export const CONFORMANCE_CONTRACT = "evalbraid_evaluation_provenance_node_conformance_v0";
const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(MODULE_DIR, "../../..");
const DEFAULT_CORE_MANIFEST = path.join(ROOT, "evalbraid", "v0", "conformance", "manifest.json");
const DEFAULT_OVERLAY_MANIFEST = path.join(ROOT, "evalbraid", "v0", "conformance", "adversarial", "manifest.json");

export function projection(outcome) {
  const pairs = outcome.result.findings.map((item) => ({ code: item.code, path: item.path }));
  const unique = new Map(pairs.map((item) => [`${item.code}\0${item.path}`, item]));
  return {
    valid: outcome.result.valid,
    record_sha256: outcome.result.record_sha256,
    schema_sha256: outcome.result.schema_sha256,
    findings: [...unique.values()].sort((left, right) =>
      left.path.localeCompare(right.path) || left.code.localeCompare(right.code)),
    exit_class: outcome.exitCode,
  };
}

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function safeRecordPath(manifestDirectory, relative) {
  const resolved = path.resolve(manifestDirectory, relative);
  const prefix = `${path.resolve(manifestDirectory)}${path.sep}`;
  if (!resolved.startsWith(prefix)) throw new Error(`record path escapes manifest directory: ${relative}`);
  return resolved;
}

function runSuite(manifestPath, kind, schemaPath) {
  const manifestBytes = fs.readFileSync(manifestPath);
  const manifestSha256 = sha256Bytes(manifestBytes);
  const manifest = loadObjectFile(manifestPath).value;
  const manifestDirectory = path.dirname(manifestPath);
  const cases = manifest.cases;
  const seen = new Set();
  const results = [];
  let attempts = 0;
  for (const specification of cases) {
    if (seen.has(specification.id)) throw new Error(`duplicate case id: ${specification.id}`);
    seen.add(specification.id);
    const recordPath = safeRecordPath(manifestDirectory, specification.record);
    const recordSha256 = sha256Bytes(fs.readFileSync(recordPath));
    const outcome = validateRecord(recordPath, schemaPath);
    attempts += outcome.networkAttempts;
    const actualProjection = projection(outcome);
    const expectedFindingPresent = specification.expected_code === undefined
      || actualProjection.findings.some((item) => item.code === specification.expected_code
        && (specification.expected_path === undefined || item.path === specification.expected_path));
    const expectedProjectionMatch = specification.expected_projection === undefined
      || sameJson(actualProjection, specification.expected_projection);
    const passed = recordSha256 === specification.record_sha256
      && outcome.stage === specification.expected
      && expectedFindingPresent
      && expectedProjectionMatch
      && actualProjection.schema_sha256 === EXPECTED_SCHEMA_SHA256;
    results.push({
      id: specification.id,
      kind,
      passed,
      expected_stage: specification.expected,
      actual_stage: outcome.stage,
      record_sha256: recordSha256,
      projection: actualProjection,
    });
  }
  return { manifestSha256, attempts, results };
}

export function runConformance({
  coreManifest = DEFAULT_CORE_MANIFEST,
  overlayManifest = DEFAULT_OVERLAY_MANIFEST,
} = {}) {
  const findings = [];
  const loadedSchema = loadSchema();
  const core = runSuite(path.resolve(coreManifest), "core", undefined);
  const overlayPresent = fs.existsSync(overlayManifest);
  const overlay = overlayPresent
    ? runSuite(path.resolve(overlayManifest), "overlay", undefined)
    : { manifestSha256: null, attempts: 0, results: [] };
  const allCases = [...core.results, ...overlay.results];
  const corePositive = core.results.filter((item) => item.expected_stage === "pass").length;
  const coreNegative = core.results.length - corePositive;
  if (core.results.length !== 29 || corePositive !== 3 || coreNegative !== 26) {
    findings.push({ code: "node_core_counts_invalid", path: "/counts/core", message: "core corpus must contain 3 positive and 26 negative cases" });
  }
  if (overlay.results.length !== 4) {
    findings.push({ code: "node_overlay_counts_invalid", path: "/counts/overlay", message: "adversarial overlay must contain exactly four cases" });
  }
  allCases.filter((item) => !item.passed).forEach((item) => {
    findings.push({ code: "node_case_failed", path: `/cases/${item.id}`, message: `${item.actual_stage} did not match the frozen expectation` });
  });
  const networkAttempts = core.attempts + overlay.attempts;
  if (networkAttempts !== 0) {
    findings.push({ code: "node_network_attempted", path: "/network_attempts", message: "validation attempted network access" });
  }
  findings.sort((left, right) => left.path.localeCompare(right.path) || left.code.localeCompare(right.code));
  return {
    contract: CONFORMANCE_CONTRACT,
    valid: findings.length === 0,
    runtime: {
      node: loadedSchema.runtime.node,
      ajv: loadedSchema.runtime.ajv,
      ajv_formats: loadedSchema.runtime.ajv_formats,
    },
    schema_sha256: loadedSchema.schemaSha256,
    manifests: {
      core_sha256: core.manifestSha256,
      overlay_sha256: overlay.manifestSha256,
    },
    counts: {
      core: {
        total: core.results.length,
        positive: corePositive,
        negative: coreNegative,
        passed: core.results.filter((item) => item.passed).length,
      },
      overlay: {
        total: overlay.results.length,
        passed: overlay.results.filter((item) => item.passed).length,
      },
    },
    network_attempts: networkAttempts,
    cases: allCases,
    findings,
  };
}

function main(argv = process.argv.slice(2)) {
  const result = runConformance();
  if (argv.includes("--json")) process.stdout.write(`${JSON.stringify(result)}\n`);
  else process.stdout.write(`${result.valid ? "PASS" : "FAIL"}: ${result.cases.filter((item) => item.passed).length}/${result.cases.length} cases; network attempts=${result.network_attempts}\n`);
  return result.valid ? 0 : 1;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  try {
    process.exitCode = main();
  } catch (error) {
    process.stderr.write(`node conformance tool error: ${error.message}\n`);
    process.exitCode = 2;
  }
}
