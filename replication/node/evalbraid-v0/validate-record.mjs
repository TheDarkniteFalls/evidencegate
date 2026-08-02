#!/usr/bin/env node
// SPDX-License-Identifier: MIT
import path from "node:path";
import { fileURLToPath } from "node:url";

import { installNetworkGuard, networkAttempts, restoreNetworkGuard } from "./deny-network.mjs";
import { loadSchema, structuralFindings } from "./schema-validator.mjs";
import { StrictJsonError, loadObjectFile } from "./strict-json.mjs";
import { finding, semanticFindings, stableResult } from "./semantic-validator.mjs";

export function validateRecord(recordPath, schemaPath) {
  installNetworkGuard();
  let schemaSha256 = "";
  try {
    let loadedSchema;
    try {
      loadedSchema = loadSchema(schemaPath);
      schemaSha256 = loadedSchema.schemaSha256;
    } catch (error) {
      return {
        stage: "tool_error",
        exitCode: 2,
        result: stableResult({
          recordSha256: null,
          schemaSha256,
          findings: [finding("profile_tool_error", "", `schema initialization failed: ${error.message}`)],
        }),
        networkAttempts: networkAttempts(),
      };
    }

    let loadedRecord;
    try {
      loadedRecord = loadObjectFile(recordPath);
    } catch (error) {
      if (error instanceof StrictJsonError) {
        return {
          stage: "load_error",
          exitCode: 2,
          result: stableResult({
            recordSha256: error.recordSha256 || null,
            schemaSha256,
            findings: [finding(error.code, "", error.message)],
          }),
          networkAttempts: networkAttempts(),
        };
      }
      return {
        stage: "tool_error",
        exitCode: 2,
        result: stableResult({
          recordSha256: null,
          schemaSha256,
          findings: [finding("profile_tool_error", "", `record load failed: ${error.message}`)],
        }),
        networkAttempts: networkAttempts(),
      };
    }

    const schemaFindings = structuralFindings(loadedSchema.validate, loadedRecord.value);
    if (schemaFindings.length) {
      return {
        stage: "schema_error",
        exitCode: 1,
        result: stableResult({
          recordSha256: loadedRecord.recordSha256,
          schemaSha256,
          findings: schemaFindings,
        }),
        networkAttempts: networkAttempts(),
      };
    }

    const relationshipFindings = semanticFindings(loadedRecord.value);
    if (relationshipFindings.length) {
      return {
        stage: "semantic_error",
        exitCode: 1,
        result: stableResult({
          recordSha256: loadedRecord.recordSha256,
          schemaSha256,
          findings: relationshipFindings,
        }),
        networkAttempts: networkAttempts(),
      };
    }
    return {
      stage: "pass",
      exitCode: 0,
      result: stableResult({ recordSha256: loadedRecord.recordSha256, schemaSha256, findings: [] }),
      networkAttempts: networkAttempts(),
    };
  } finally {
    restoreNetworkGuard();
  }
}

function main(argv = process.argv.slice(2)) {
  const json = argv.includes("--json");
  const positional = argv.filter((argument) => argument !== "--json");
  if (positional.length !== 1) {
    process.stderr.write("usage: validate-record.mjs RECORD [--json]\n");
    return 2;
  }
  const outcome = validateRecord(path.resolve(positional[0]));
  if (json) process.stdout.write(`${JSON.stringify(outcome.result)}\n`);
  else {
    process.stdout.write(`${outcome.stage}: ${outcome.result.valid ? "valid" : "invalid"}\n`);
    outcome.result.findings.forEach((item) => process.stdout.write(`${item.code} ${item.path}: ${item.message}\n`));
  }
  return outcome.exitCode;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) process.exitCode = main();
