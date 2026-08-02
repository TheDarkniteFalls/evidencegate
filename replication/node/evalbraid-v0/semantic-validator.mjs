// SPDX-License-Identifier: MIT

export const CONTRACT = "evalbraid_evaluation_provenance_result_v0";
export const PROFILE = "evalbraid_evaluation_provenance_v0";
export const CORE_LAYERS = new Set([
  "trajectory_agent_self_check",
  "verifier_definition",
  "executed_verifier",
  "handoff_lifecycle",
]);

export function finding(code, path, message) {
  return { code, path, message };
}

export function sortFindings(findings) {
  const unique = new Map();
  for (const item of findings) unique.set(`${item.code}\0${item.path}\0${item.message}`, item);
  return [...unique.values()].sort((left, right) =>
    left.path.localeCompare(right.path)
      || left.code.localeCompare(right.code)
      || left.message.localeCompare(right.message));
}

export function stableResult({ recordSha256, schemaSha256, findings }) {
  const ordered = sortFindings(findings);
  return {
    contract: CONTRACT,
    valid: ordered.length === 0,
    profile: PROFILE,
    record_sha256: recordSha256,
    schema_sha256: schemaSha256,
    findings: ordered,
  };
}

function escapePointer(token) {
  return String(token).replaceAll("~", "~0").replaceAll("/", "~1");
}

function pointer(parts) {
  return parts.length === 0 ? "" : `/${parts.map(escapePointer).join("/")}`;
}

function observedValue(field) {
  return field && typeof field === "object" && field.status === "observed" ? field.value : null;
}

function expectedLayer(path) {
  if (path.startsWith("/trajectory/")) return "trajectory_agent_self_check";
  if (path.startsWith("/agent_handoff/")) return "handoff_lifecycle";
  if (path.startsWith("/verifier_definition/policy_references")) return "policy";
  if (path.startsWith("/verifier_definition/")) return "verifier_definition";
  if (path.startsWith("/verifier_start/") || path.startsWith("/verifier_result/")) return "executed_verifier";
  if (path.startsWith("/measurements/")) return "executed_verifier";
  if (path.startsWith("/evaluation_judgment/integrity_basis/policy_references")) return "policy";
  if (path.startsWith("/adjudication/")) return "adjudication";
  return null;
}

function referenceUses(record) {
  const uses = [];
  function walk(value, parts) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [key, child] of Object.entries(value)) {
        const childParts = [...parts, key];
        const childPath = pointer(childParts);
        if (["evidence_references", "basis_references", "policy_references"].includes(key)) {
          if (Array.isArray(child)) {
            const expected = expectedLayer(childPath);
            child.forEach((referenceId, index) => {
              if (typeof referenceId === "string") uses.push([referenceId, pointer([...childParts, index]), expected]);
            });
          }
        } else {
          walk(child, childParts);
        }
      }
    } else if (Array.isArray(value)) {
      value.forEach((child, index) => walk(child, [...parts, index]));
    }
  }
  for (const [key, value] of Object.entries(record)) {
    if (key !== "source_references") walk(value, [key]);
  }
  return uses;
}

function resolvePointer(record, value) {
  if (!value.startsWith("/")) return [false, null];
  let current = record;
  for (const rawSegment of value.slice(1).split("/")) {
    if (/(?:~(?![01]))/.test(rawSegment)) return [false, null];
    const segment = rawSegment.replaceAll("~1", "/").replaceAll("~0", "~");
    if (Array.isArray(current)) {
      if (!/^(?:0|[1-9]\d*)$/.test(segment)) return [false, null];
      const index = Number(segment);
      if (!Number.isSafeInteger(index) || index >= current.length) return [false, null];
      current = current[index];
    } else if (current && typeof current === "object") {
      if (!Object.hasOwn(current, segment)) return [false, null];
      current = current[segment];
    } else {
      return [false, null];
    }
  }
  return [true, current];
}

function deepEqual(left, right) {
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) && Array.isArray(right)) {
    return left.length === right.length && left.every((item, index) => deepEqual(item, right[index]));
  }
  if (left && right && typeof left === "object" && typeof right === "object"
      && !Array.isArray(left) && !Array.isArray(right)) {
    const leftKeys = Object.keys(left).sort();
    const rightKeys = Object.keys(right).sort();
    return deepEqual(leftKeys, rightKeys) && leftKeys.every((key) => deepEqual(left[key], right[key]));
  }
  return false;
}

export function semanticFindings(record) {
  const findings = [];
  const sources = record.source_references;
  const counts = new Map();
  const firstSource = new Map();
  const firstIndex = new Map();
  sources.forEach((source, index) => {
    counts.set(source.reference_id, (counts.get(source.reference_id) || 0) + 1);
    if (!firstSource.has(source.reference_id)) firstSource.set(source.reference_id, source);
    if (!firstIndex.has(source.reference_id)) firstIndex.set(source.reference_id, index);
  });

  sources.forEach((source, index) => {
    if (counts.get(source.reference_id) > 1 && firstIndex.get(source.reference_id) !== index) {
      findings.push(finding(
        "profile_reference_duplicate",
        `/source_references/${index}/reference_id`,
        "reference_id duplicates an earlier source reference",
      ));
    }
  });

  const usedIds = new Set();
  for (const [referenceId, path, requiredLayer] of referenceUses(record)) {
    const source = firstSource.get(referenceId);
    if (!source) {
      findings.push(finding("profile_reference_unresolved", path, "reference id does not resolve within source_references"));
      continue;
    }
    usedIds.add(referenceId);
    if (requiredLayer !== null && source.layer !== requiredLayer) {
      findings.push(finding(
        "profile_reference_layer_invalid",
        path,
        `section requires a ${requiredLayer} source reference`,
      ));
    }
  }

  sources.forEach((source, index) => {
    if (!usedIds.has(source.reference_id)) {
      findings.push(finding(
        "profile_reference_orphaned",
        `/source_references/${index}/reference_id`,
        "source reference is not used by a semantic section",
      ));
    }
  });

  const presentLayers = new Set(sources.map((source) => source.layer));
  [...CORE_LAYERS].filter((layer) => !presentLayers.has(layer)).sort().forEach((layer) => {
    findings.push(finding(
      "profile_layer_missing",
      "/source_references",
      `required core evidence layer is missing: ${layer}`,
    ));
  });

  sources.forEach((source, index) => {
    if (source.availability === "available" && source.digest.status !== "observed") {
      findings.push(finding(
        "profile_source_availability_invalid",
        `/source_references/${index}/availability`,
        "available evidence requires an observed digest",
      ));
    } else if (source.availability === "not_observed" && source.digest.status === "observed") {
      findings.push(finding(
        "profile_source_availability_invalid",
        `/source_references/${index}/availability`,
        "not_observed evidence cannot present an observed digest",
      ));
    }
  });

  const identityDigest = observedValue(record.identity.verifier_digest);
  const definitionDigest = observedValue(record.verifier_definition.verifier_digest);
  if (identityDigest !== null && definitionDigest !== null && identityDigest !== definitionDigest) {
    findings.push(finding(
      "profile_verifier_digest_mismatch",
      "/verifier_definition/verifier_digest/value",
      "verifier definition digest differs from the identity digest",
    ));
  }

  const handoff = record.agent_handoff;
  const artifactIds = new Set(handoff.relevant_artifacts.map((item) => item.artifact_id));
  const processIds = new Set(handoff.relevant_processes.map((item) => item.process_id));
  record.verifier_start.liveness_observations.forEach((observation, index) => {
    const knownIds = observation.subject_kind === "artifact" ? artifactIds : processIds;
    if (!knownIds.has(observation.subject_id)) {
      findings.push(finding(
        "profile_handoff_link_mismatch",
        `/verifier_start/liveness_observations/${index}/subject_id`,
        "verifier-start subject does not match a same-kind handoff subject",
      ));
    }
  });

  const exitValue = observedValue(handoff.agent_exit_time);
  const startValue = observedValue(record.verifier_start.timestamp);
  const adjudication = record.adjudication;
  const adjudicationValue = observedValue(adjudication.timestamp);
  const exitTime = typeof exitValue === "string" ? Date.parse(exitValue) : null;
  const startTime = typeof startValue === "string" ? Date.parse(startValue) : null;
  const adjudicationTime = typeof adjudicationValue === "string" ? Date.parse(adjudicationValue) : null;
  if (exitTime !== null && startTime !== null && exitTime > startTime) {
    findings.push(finding(
      "profile_time_order_invalid",
      "/verifier_start/timestamp/value",
      "observed verifier start precedes observed agent exit",
    ));
  }
  if (adjudication.status === "resolved" && adjudicationTime !== null) {
    const evidenceTimes = [exitTime, startTime].filter((value) => value !== null);
    if (evidenceTimes.length && adjudicationTime < Math.max(...evidenceTimes)) {
      findings.push(finding(
        "profile_time_order_invalid",
        "/adjudication/timestamp/value",
        "resolved adjudication precedes observed evidence timing",
      ));
    }
  }

  const judgment = record.evaluation_judgment;
  const judgmentUsesSelfCheck = referenceUses(record).some(([referenceId, path]) =>
    path.startsWith("/evaluation_judgment/")
      && firstSource.has(referenceId)
      && firstSource.get(referenceId).layer === "trajectory_agent_self_check");
  if (judgment.evidence_independence === "independent" && judgmentUsesSelfCheck) {
    findings.push(finding(
      "profile_judgment_independence_invalid",
      "/evaluation_judgment/evidence_independence",
      "independent judgment cannot rely on trajectory_agent_self_check evidence",
    ));
  }
  const expectedTriggers = new Set();
  const triggerFields = [
    [judgment.reward_alignment === "possible_mismatch", "possible_mismatch"],
    [judgment.reward_alignment === "confirmed_mismatch", "confirmed_mismatch"],
    [judgment.integrity_signal === "ambiguous", "ambiguous_integrity_signal"],
    [judgment.integrity_signal === "possible_shortcut", "possible_shortcut"],
    [judgment.integrity_signal === "confirmed_shortcut", "confirmed_shortcut"],
    [judgment.confidence === "low", "low_confidence_core_judgment"],
    [judgment.claim_severity === "high", "high_severity_claim"],
  ];
  triggerFields.forEach(([condition, trigger]) => { if (condition) expectedTriggers.add(trigger); });
  const actualTriggers = new Set(adjudication.triggers);
  const triggersEqual = actualTriggers.size === expectedTriggers.size
    && [...actualTriggers].every((trigger) => expectedTriggers.has(trigger));
  if (!triggersEqual) {
    findings.push(finding(
      "profile_trigger_set_invalid",
      "/adjudication/triggers",
      "adjudication triggers do not equal the frozen judgment-derived set",
    ));
  }
  if (adjudication.triggered !== Boolean(expectedTriggers.size)) {
    findings.push(finding(
      "profile_trigger_set_invalid",
      "/adjudication/triggered",
      "adjudication triggered flag does not match the frozen trigger set",
    ));
  }

  const pointerValidity = new Map();
  for (const collection of ["retained_fields", "revised_fields"]) {
    adjudication[collection].forEach((entry, index) => {
      const path = collection === "retained_fields" ? entry : entry.path;
      const [resolved, value] = resolvePointer(record, path);
      const allowed = path.startsWith("/evaluation_judgment/");
      pointerValidity.set(path, [resolved && allowed, value]);
      if (!resolved || !allowed) {
        const suffix = collection === "retained_fields" ? "" : "/path";
        findings.push(finding(
          "profile_adjudication_pointer_invalid",
          `/adjudication/${collection}/${index}${suffix}`,
          "path must resolve to a field below evaluation_judgment",
        ));
      }
    });
  }

  adjudication.revised_fields.forEach((revision, index) => {
    const [validPointer, finalValue] = pointerValidity.get(revision.path) || [false, null];
    if (!validPointer) return;
    if (deepEqual(revision.prior_value, revision.revised_value) || !deepEqual(finalValue, revision.revised_value)) {
      findings.push(finding(
        "profile_revision_value_invalid",
        `/adjudication/revised_fields/${index}`,
        "revision must change the prior value and equal the final record value",
      ));
    }
  });

  judgment.proven_facts.forEach((fact, index) => {
    const available = fact.evidence_references.some((referenceId) =>
      firstSource.has(referenceId) && firstSource.get(referenceId).availability === "available");
    if (!available) {
      findings.push(finding(
        "profile_proven_fact_evidence_invalid",
        `/evaluation_judgment/proven_facts/${index}/evidence_references`,
        "proven fact requires at least one resolved, available source reference",
      ));
    }
  });

  const sourceRank = { internal_only: 0, reference_only: 1, cleared: 2 };
  const recordRank = { internal_only: 0, review_required: 1, cleared: 2 };
  let allowedRank = Math.min(...sources.map((source) => sourceRank[source.redistribution]), 2);
  const handling = record.data_handling;
  if (["internal", "confidential"].includes(handling.classification)
      || ["contains_personal_data", "contains_secrets", "contains_raw_trajectory", "contains_task_assets"]
        .some((field) => handling[field])) {
    allowedRank = Math.min(allowedRank, 0);
  }
  if (recordRank[handling.redistribution_status] > allowedRank) {
    findings.push(finding(
      "profile_redistribution_invalid",
      "/data_handling/redistribution_status",
      "record redistribution exceeds a cited source or content restriction",
    ));
  }

  record.trajectory.self_checks.forEach((check, index) => {
    if (check.independence !== "self_authored") {
      findings.push(finding(
        "profile_self_check_independence_invalid",
        `/trajectory/self_checks/${index}/independence`,
        "agent self-checks must remain self_authored",
      ));
    }
  });

  return sortFindings(findings);
}
