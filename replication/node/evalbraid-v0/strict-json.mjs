// SPDX-License-Identifier: MIT
import fs from "node:fs";
import crypto from "node:crypto";

export const MAX_RECORD_BYTES = 2 * 1024 * 1024;
export const MAX_NESTING_DEPTH = 256;

export class StrictJsonError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "StrictJsonError";
    this.code = code;
  }
}

function requireJson(condition, code, message) {
  if (!condition) throw new StrictJsonError(code, message);
}

export function sha256Bytes(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

export function strictParse(text) {
  let index = 0;

  function whitespace() {
    while (/[\x20\t\r\n]/.test(text[index] ?? "")) index += 1;
  }

  function parseString() {
    requireJson(text[index] === '"', "profile_load_json_invalid", `expected JSON string at character ${index}`);
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
        let value;
        try {
          value = JSON.parse(text.slice(start, index));
        } catch {
          throw new StrictJsonError("profile_load_json_invalid", `invalid JSON string at character ${start}`);
        }
        for (let offset = 0; offset < value.length; offset += 1) {
          const code = value.charCodeAt(offset);
          if (code >= 0xd800 && code <= 0xdbff) {
            const next = value.charCodeAt(offset + 1);
            requireJson(
              next >= 0xdc00 && next <= 0xdfff,
              "profile_load_invalid_unicode",
              "unpaired Unicode surrogate is not allowed",
            );
            offset += 1;
          } else {
            requireJson(
              !(code >= 0xdc00 && code <= 0xdfff),
              "profile_load_invalid_unicode",
              "unpaired Unicode surrogate is not allowed",
            );
          }
        }
        return value;
      }
    }
    throw new StrictJsonError("profile_load_json_invalid", "unterminated JSON string");
  }

  function parseValue(depth = 0) {
    requireJson(
      depth <= MAX_NESTING_DEPTH,
      "profile_load_nesting_too_deep",
      `JSON nesting exceeds ${MAX_NESTING_DEPTH}`,
    );
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
    requireJson(match, "profile_load_json_invalid", `unexpected JSON token at character ${index}`);
    index += match[0].length;
    const number = Number(match[0]);
    requireJson(Number.isFinite(number), "profile_load_number_invalid", "non-finite JSON number is not allowed");
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
      requireJson(!keys.has(key), "profile_load_duplicate_key", `duplicate object key: ${key}`);
      keys.add(key);
      whitespace();
      requireJson(text[index] === ":", "profile_load_json_invalid", `expected ':' at character ${index}`);
      index += 1;
      result[key] = parseValue(depth);
      whitespace();
      if (text[index] === "}") {
        index += 1;
        return result;
      }
      requireJson(text[index] === ",", "profile_load_json_invalid", `expected ',' at character ${index}`);
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
      requireJson(text[index] === ",", "profile_load_json_invalid", `expected ',' at character ${index}`);
      index += 1;
    }
  }

  const value = parseValue();
  whitespace();
  requireJson(index === text.length, "profile_load_json_invalid", `unexpected trailing JSON at character ${index}`);
  requireJson(
    value !== null && typeof value === "object" && !Array.isArray(value),
    "profile_load_top_level_invalid",
    "record must contain one top-level JSON object",
  );
  return value;
}

export function loadObjectFile(filename, { maxBytes = MAX_RECORD_BYTES } = {}) {
  const stat = fs.statSync(filename);
  if (stat.size > maxBytes) {
    throw new StrictJsonError("profile_load_too_large", `record exceeds the ${maxBytes}-byte limit`);
  }
  const bytes = fs.readFileSync(filename);
  const recordSha256 = sha256Bytes(bytes);
  if (bytes.length > maxBytes) {
    throw new StrictJsonError("profile_load_too_large", "record changed beyond the byte limit while reading");
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (error) {
    throw new StrictJsonError("profile_load_utf8_invalid", `record is not UTF-8: ${error.message}`);
  }
  try {
    return { value: strictParse(text), bytes, recordSha256 };
  } catch (error) {
    if (error instanceof StrictJsonError) error.recordSha256 = recordSha256;
    throw error;
  }
}
