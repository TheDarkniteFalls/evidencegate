// SPDX-License-Identifier: MIT
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import { sha256Bytes, strictParse } from "./strict-json.mjs";

export const EXPECTED_NODE_VERSION = "24.14.0";
export const EXPECTED_AJV_VERSION = "8.20.0";
export const EXPECTED_AJV_FORMATS_VERSION = "3.0.1";
export const EXPECTED_SCHEMA_SHA256 = "a73118a8e44980a4f0c1cac7b57ec49db581c796cbeb6c3ca108281bc4daef78";

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));
export const CANDIDATE_ROOT = path.resolve(MODULE_DIR, "../../..");
export const DEFAULT_SCHEMA = path.join(CANDIDATE_ROOT, "schemas", "evalbraid-evaluation-provenance-v0.schema.json");
export const DEFAULT_NODE_ENV = MODULE_DIR;

function packageRuntime() {
  const nodeEnv = path.resolve(process.env.EVALBRAID_NODE_ENV || DEFAULT_NODE_ENV);
  const packageJson = path.join(nodeEnv, "package.json");
  if (!fs.existsSync(packageJson)) {
    throw new Error(`Node dependency environment is missing: ${nodeEnv}`);
  }
  const require = createRequire(packageJson);
  const ajvPackage = require("ajv/package.json");
  const formatsPackage = require("ajv-formats/package.json");
  if (process.versions.node !== EXPECTED_NODE_VERSION) {
    throw new Error(`Node ${EXPECTED_NODE_VERSION} required; found ${process.versions.node}`);
  }
  if (ajvPackage.version !== EXPECTED_AJV_VERSION || formatsPackage.version !== EXPECTED_AJV_FORMATS_VERSION) {
    throw new Error(
      `locked Ajv dependencies required; found ajv ${ajvPackage.version}, ajv-formats ${formatsPackage.version}`,
    );
  }
  const AjvModule = require("ajv/dist/2020.js");
  const addFormatsModule = require("ajv-formats");
  return {
    nodeEnv,
    Ajv2020: AjvModule.default || AjvModule,
    addFormats: addFormatsModule.default || addFormatsModule,
    versions: {
      node: process.versions.node,
      ajv: ajvPackage.version,
      ajv_formats: formatsPackage.version,
    },
  };
}

function pointerEscape(value) {
  return String(value).replaceAll("~", "~0").replaceAll("/", "~1");
}

function normalizedSchemaPath(error) {
  if (error.keyword === "required" && error.params?.missingProperty) {
    return error.instancePath;
  }
  return error.instancePath || "";
}

export function loadSchema(schemaPath = DEFAULT_SCHEMA) {
  const runtime = packageRuntime();
  const bytes = fs.readFileSync(schemaPath);
  const schemaSha256 = sha256Bytes(bytes);
  if (schemaSha256 !== EXPECTED_SCHEMA_SHA256) {
    throw new Error(`schema SHA-256 mismatch: ${schemaSha256}`);
  }
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  const schema = strictParse(text);
  const ajv = new runtime.Ajv2020({
    allErrors: true,
    strictSchema: true,
    strictTypes: false,
    strictTuples: false,
    strictRequired: false,
    validateFormats: true,
  });
  runtime.addFormats(ajv, ["uuid", "date-time", "uri"]);
  if (!ajv.validateSchema(schema)) {
    throw new Error(`Draft 2020-12 metaschema validation failed: ${ajv.errorsText(ajv.errors)}`);
  }
  const validate = ajv.compile(schema);
  return { schema, schemaSha256, validate, runtime: runtime.versions, nodeEnv: runtime.nodeEnv };
}

export function structuralFindings(validate, record) {
  if (validate(record)) return [];
  const errors = (validate.errors || []).filter((error) =>
    error.keyword !== "if" && !error.schemaPath.includes("/contains/const"));
  return errors.map((error) => ({
    code: "profile_schema_invalid",
    path: normalizedSchemaPath(error),
    message: error.message || `schema validation failed for ${pointerEscape(error.keyword)}`,
  }));
}

export function runFormatProbes(schemaPath = DEFAULT_SCHEMA) {
  const loaded = loadSchema(schemaPath);
  const runtime = packageRuntime();
  const ajv = new runtime.Ajv2020({ strict: true, validateFormats: true });
  runtime.addFormats(ajv, ["uuid", "date-time", "uri"]);
  const probes = {
    uuid: ajv.validate({ type: "string", format: "uuid" }, "123e4567-e89b-12d3-a456-426614174000")
      && !ajv.validate({ type: "string", format: "uuid" }, "not-a-uuid"),
    date_time: ajv.validate({ type: "string", format: "date-time" }, "2026-07-26T00:00:00Z")
      && !ajv.validate({ type: "string", format: "date-time" }, "2026-99-99"),
    uri: ajv.validate({ type: "string", format: "uri" }, "https://example.invalid/a")
      && !ajv.validate({ type: "string", format: "uri" }, "not a uri"),
  };
  return { ...loaded, probes };
}
