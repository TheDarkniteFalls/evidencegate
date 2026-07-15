#!/usr/bin/env node
// Separately written, dependency-free EvidenceGate v1 conformance consumer.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";


const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const CORPUS = path.join(ROOT, "conformance", "v1");
const MAX_BYTES = 1_000_000;
const SHA = /^[0-9a-fA-F]{40}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const CHECK_STATUSES = new Set(["passed", "failed", "skipped", "unknown"]);
const TOP_FIELDS = new Set([
  "schema_version", "summary", "subject", "scope", "files_touched", "checks",
  "claims", "risks", "human_review", "public_safety", "extensions",
]);
const SUBJECT_FIELDS = new Set(["type", "base_sha", "head_sha"]);
const SCOPE_FIELDS = new Set(["allowed_paths", "protected_prefixes"]);
const CHECK_FIELDS = new Set([
  "id", "name", "command", "status", "summary", "scope", "revision", "required",
]);
const CLAIM_FIELDS = new Set(["id", "text", "evidence_refs"]);


class ConformanceError extends Error {}


function require(condition, message) {
  if (!condition) throw new ConformanceError(message);
}


function strictParse(text) {
  let index = 0;

  function whitespace() {
    while (/[\x20\t\r\n]/.test(text[index] ?? "")) index += 1;
  }

  function parseString() {
    require(text[index] === '"', `expected JSON string at byte ${index}`);
    const start = index;
    index += 1;
    let escaped = false;
    while (index < text.length) {
      const character = text[index];
      index += 1;
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === '"') {
        const value = JSON.parse(text.slice(start, index));
        for (let offset = 0; offset < value.length; offset += 1) {
          const code = value.charCodeAt(offset);
          if (code >= 0xd800 && code <= 0xdbff) {
            const next = value.charCodeAt(offset + 1);
            require(next >= 0xdc00 && next <= 0xdfff, "unpaired Unicode surrogate is not allowed");
            offset += 1;
          } else {
            require(!(code >= 0xdc00 && code <= 0xdfff), "unpaired Unicode surrogate is not allowed");
          }
        }
        return value;
      }
    }
    throw new ConformanceError("unterminated JSON string");
  }

  function parseValue(depth = 0) {
    require(depth <= 256, "packet JSON nesting is too deep");
    whitespace();
    const character = text[index];
    if (character === '"') return parseString();
    if (character === "{") return parseObject(depth + 1);
    if (character === "[") return parseArray(depth + 1);
    for (const [token, value] of [["true", true], ["false", false], ["null", null]]) {
      if (text.startsWith(token, index)) {
        index += token.length;
        return value;
      }
    }
    const match = text.slice(index).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    require(match, `unexpected JSON token at byte ${index}`);
    index += match[0].length;
    const number = Number(match[0]);
    require(Number.isFinite(number), "non-finite JSON number is not allowed");
    return number;
  }

  function parseObject(depth) {
    index += 1;
    whitespace();
    const result = {};
    const keys = new Set();
    if (text[index] === "}") {
      index += 1;
      return result;
    }
    while (true) {
      whitespace();
      const key = parseString();
      require(!keys.has(key), `duplicate JSON object key: ${key}`);
      keys.add(key);
      whitespace();
      require(text[index] === ":", `expected ':' at byte ${index}`);
      index += 1;
      result[key] = parseValue(depth);
      whitespace();
      if (text[index] === "}") {
        index += 1;
        return result;
      }
      require(text[index] === ",", `expected ',' at byte ${index}`);
      index += 1;
    }
  }

  function parseArray(depth) {
    index += 1;
    whitespace();
    const result = [];
    if (text[index] === "]") {
      index += 1;
      return result;
    }
    while (true) {
      result.push(parseValue(depth));
      whitespace();
      if (text[index] === "]") {
        index += 1;
        return result;
      }
      require(text[index] === ",", `expected ',' at byte ${index}`);
      index += 1;
    }
  }

  const value = parseValue();
  whitespace();
  require(index === text.length, `unexpected trailing JSON at byte ${index}`);
  return value;
}


function loadObject(filename) {
  const bytes = fs.readFileSync(filename);
  require(bytes.length <= MAX_BYTES, `packet exceeds ${MAX_BYTES} bytes`);
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  const value = strictParse(text);
  require(value !== null && typeof value === "object" && !Array.isArray(value), "packet must be a JSON object");
  return value;
}


function text(value) {
  return typeof value === "string" && /\S/.test(value);
}


function safePath(value) {
  return text(value)
    && value === value.trim()
    && !value.startsWith("/")
    && !value.includes("\\")
    && !value.includes("//")
    && !/[\u0000-\u001f]/.test(value)
    && value.split("/").every((part) => part && part !== "." && part !== "..");
}


function unknownFields(value, allowed, location, errors) {
  for (const key of Object.keys(value).sort()) {
    if (!allowed.has(key)) {
      const field = location ? `${location}.${key}` : key;
      errors.push(`${field} is not defined by EvidenceGate v1; put non-authoritative metadata under extensions`);
    }
  }
}


function pathList(value, location, errors, nonempty = false) {
  if (!Array.isArray(value) || (nonempty && value.length === 0)) {
    errors.push(`${location} must be ${nonempty ? "a non-empty" : "a"} list of relative Git paths`);
    return [];
  }
  value.forEach((item, offset) => {
    if (!safePath(item)) errors.push(`${location}[${offset + 1}] must be a safe relative Git path`);
  });
  if (new Set(value).size !== value.length) errors.push(`${location} must not contain duplicate paths`);
  return value.filter(safePath);
}


function validate(packet) {
  const errors = [];
  unknownFields(packet, TOP_FIELDS, "", errors);
  if (packet.schema_version !== 1) errors.push("schema_version must be 1");
  if (!text(packet.summary)) errors.push("summary must be non-empty text");

  let head = null;
  if (!packet.subject || typeof packet.subject !== "object" || Array.isArray(packet.subject)) {
    errors.push("subject must be an object");
  } else {
    unknownFields(packet.subject, SUBJECT_FIELDS, "subject", errors);
    if (packet.subject.type !== "git_change") errors.push("subject.type must be git_change");
    if (!SHA.test(packet.subject.base_sha ?? "")) errors.push("subject.base_sha must be a full 40-character Git commit SHA");
    if (!SHA.test(packet.subject.head_sha ?? "")) errors.push("subject.head_sha must be a full 40-character Git commit SHA");
    if (SHA.test(packet.subject.head_sha ?? "")) head = packet.subject.head_sha.toLowerCase();
    if (packet.subject.base_sha?.toLowerCase() === head) errors.push("subject.base_sha and subject.head_sha must differ");
  }

  const files = pathList(packet.files_touched, "files_touched", errors, true);
  let allowed = [];
  let protectedPrefixes = [];
  if (!packet.scope || typeof packet.scope !== "object" || Array.isArray(packet.scope)) {
    errors.push("scope must be an object");
  } else {
    unknownFields(packet.scope, SCOPE_FIELDS, "scope", errors);
    allowed = pathList(packet.scope.allowed_paths, "scope.allowed_paths", errors, true);
    protectedPrefixes = pathList(packet.scope.protected_prefixes, "scope.protected_prefixes", errors);
  }
  const outside = files.filter((item) => !allowed.includes(item)).sort();
  if (outside.length) errors.push(`files_touched outside scope.allowed_paths: ${outside.join(", ")}`);
  const protectedFiles = files.filter((item) => protectedPrefixes.some((prefix) => item === prefix || item.startsWith(`${prefix}/`))).sort();
  if (protectedFiles.length) errors.push(`files_touched include protected paths: ${protectedFiles.join(", ")}`);

  const checks = new Map();
  if (!Array.isArray(packet.checks) || packet.checks.length === 0) {
    errors.push("checks must be a non-empty list");
  } else {
    packet.checks.forEach((check, offset) => {
      const location = `checks[${offset + 1}]`;
      if (!check || typeof check !== "object" || Array.isArray(check)) {
        errors.push(`${location} must be an object`);
        return;
      }
      unknownFields(check, CHECK_FIELDS, location, errors);
      if (!ID.test(check.id ?? "")) errors.push(`${location}.id is invalid`);
      for (const field of ["name", "command", "summary", "scope"]) {
        if (!text(check[field])) errors.push(`${location}.${field} must be non-empty text`);
      }
      if (!CHECK_STATUSES.has(check.status)) errors.push(`${location}.status is unsupported`);
      if (!SHA.test(check.revision ?? "")) errors.push(`${location}.revision must be a full Git SHA`);
      if (typeof check.required !== "boolean") errors.push(`${location}.required must be true or false`);
      if (checks.has(check.id)) errors.push(`duplicate check id: ${check.id}`);
      else checks.set(check.id, check);
      if (head && SHA.test(check.revision ?? "") && check.revision.toLowerCase() !== head) {
        errors.push(`${location}.revision does not match subject.head_sha`);
      }
    });
  }

  const claimIds = new Set();
  if (!Array.isArray(packet.claims) || packet.claims.length === 0) {
    errors.push("claims must be a non-empty list");
  } else {
    packet.claims.forEach((claim, offset) => {
      const location = `claims[${offset + 1}]`;
      if (!claim || typeof claim !== "object" || Array.isArray(claim)) {
        errors.push(`${location} must be an object`);
        return;
      }
      unknownFields(claim, CLAIM_FIELDS, location, errors);
      if (!ID.test(claim.id ?? "")) errors.push(`${location}.id is invalid`);
      if (claimIds.has(claim.id)) errors.push(`duplicate claim id: ${claim.id}`);
      claimIds.add(claim.id);
      if (!text(claim.text)) errors.push(`${location}.text must be non-empty text`);
      if (!Array.isArray(claim.evidence_refs) || claim.evidence_refs.length === 0) {
        errors.push(`${location}.evidence_refs must be a non-empty list`);
        return;
      }
      claim.evidence_refs.forEach((reference) => {
        const check = checks.get(reference);
        if (!check) errors.push(`${location} references unknown evidence: ${reference}`);
        else if (check.status !== "passed") errors.push(`${location} references non-passing evidence: ${reference} (${check.status})`);
      });
    });
  }
  if (!Array.isArray(packet.risks) || packet.risks.length === 0 || !packet.risks.every(text)) errors.push("risks must be a non-empty list of text");
  for (const [field, statuses] of [
    ["human_review", new Set(["approved", "changes_requested", "pending"])],
    ["public_safety", new Set(["reviewed", "pending", "not_applicable"])],
  ]) {
    const value = packet[field];
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      errors.push(`${field} must be an object`);
      continue;
    }
    if (!statuses.has(value.status)) errors.push(`${field}.status is unsupported`);
    if (!SHA.test(value.reviewed_head_sha ?? "")) errors.push(`${field}.reviewed_head_sha must be a full Git SHA`);
    if (head && SHA.test(value.reviewed_head_sha ?? "") && value.reviewed_head_sha.toLowerCase() !== head) errors.push(`${field}.reviewed_head_sha does not match subject.head_sha`);
    if (!text(value.summary)) errors.push(`${field}.summary must be non-empty text`);
  }
  if (!text(packet.human_review?.reviewer)) errors.push("human_review.reviewer must be non-empty text");
  if (packet.extensions !== undefined && (!packet.extensions || typeof packet.extensions !== "object" || Array.isArray(packet.extensions))) errors.push("extensions must be an object when present");
  return errors;
}


function markdownText(value) {
  return String(value).trim().split(/\s+/).join(" ")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replace(/[\\`*_{}\[\]()#!|>]/g, "\\$&");
}


function render(packet) {
  const lines = [
    "# EvidenceGate v1 receipt", "", "## Summary", "", `> ${markdownText(packet.summary)}`,
    "", "## Checks", "",
  ];
  for (const check of packet.checks) lines.push(`- ${markdownText(check.id)} ${markdownText(check.summary)}`);
  lines.push("", "## Claims", "");
  for (const claim of packet.claims) lines.push(`- ${markdownText(claim.id)} ${markdownText(claim.text)}`);
  lines.push("", "## Human review", "", `- Reviewer: ${markdownText(packet.human_review.reviewer)}`);
  lines.push("", "## Public-safety review", "", `- Summary: ${markdownText(packet.public_safety.summary)}`);
  return `${lines.join("\n")}\n`;
}


function findingCode(message, phase) {
  if (phase === "load") return "packet_load_error";
  if (message.startsWith("schema_version")) return "receipt_version_invalid";
  if (message.includes("revision does not match subject.head_sha")
      || message.includes("reviewed_head_sha does not match subject.head_sha")
      || message.startsWith("subject.base_sha")
      || message.startsWith("subject.head_sha")) return "receipt_revision_invalid";
  if (message.startsWith("files_touched") || message.startsWith("scope.")
      || message.includes("protected paths")) return "receipt_scope_invalid";
  if (message.startsWith("checks") || message.startsWith("claims")
      || message.startsWith("duplicate check id")
      || message.startsWith("duplicate claim id")) return "receipt_evidence_invalid";
  return "receipt_structure_invalid";
}


function checkCase(specification) {
  const filename = path.join(CORPUS, specification.receipt);
  let packet;
  try {
    packet = loadObject(filename);
  } catch (error) {
    require(specification.expected === "load_error", `${specification.id}: unexpected load error: ${error.message}`);
    require(!specification.expected_code || findingCode(error.message, "load") === specification.expected_code, `${specification.id}: wrong load error code`);
    require(!specification.contains || error.message.includes(specification.contains), `${specification.id}: load error did not contain ${specification.contains}`);
    return;
  }
  require(specification.expected !== "load_error", `${specification.id}: expected a load error`);
  const errors = validate(packet);
  if (specification.expected === "validation_error") {
    require(errors.length > 0, `${specification.id}: expected validation errors`);
    const codes = new Set(errors.map((error) => findingCode(error, "validation")));
    require(!specification.expected_code || codes.has(specification.expected_code), `${specification.id}: wrong validation error code`);
    require(!specification.contains || errors.some((error) => error.includes(specification.contains)), `${specification.id}: validation errors did not contain ${specification.contains}: ${errors}`);
    return;
  }
  require(errors.length === 0, `${specification.id}: unexpected validation errors: ${errors}`);
  if (specification.render) {
    const rendered = render(packet);
    const count = rendered.split(specification.render.heading).length - 1;
    require(count === specification.render.heading_count, `${specification.id}: wrong heading count`);
    for (const forbidden of specification.render.forbidden) require(!rendered.includes(forbidden), `${specification.id}: rendered forbidden structure ${forbidden}`);
  }
}


function main() {
  try {
    const manifest = loadObject(path.join(CORPUS, "manifest.json"));
    require(manifest.schema_version === "evidencegate_conformance_v1", "unsupported manifest");
    require(manifest.cli_result_contract === "evidencegate_cli_result_v1", "unsupported CLI result contract");
    require(Array.isArray(manifest.cases) && manifest.cases.length > 0, "manifest cases required");
    const seen = new Set();
    for (const specification of manifest.cases) {
      require(!seen.has(specification.id), `duplicate conformance case id: ${specification.id}`);
      seen.add(specification.id);
      checkCase(specification);
      console.log(`PASS node conformance ${specification.id}`);
    }
    console.log("PASS node_conformance_v1");
    return 0;
  } catch (error) {
    console.log(`FAIL node_conformance_v1: ${error.message}`);
    return 1;
  }
}


process.exitCode = main();
