// SPDX-License-Identifier: MIT

let attempts = 0;
let originalFetch;

function deny() {
  attempts += 1;
  throw new Error("network access is disabled during conformance validation");
}

export function installNetworkGuard() {
  attempts = 0;
  originalFetch = globalThis.fetch;
  globalThis.fetch = deny;
}

export function restoreNetworkGuard() {
  if (originalFetch === undefined) delete globalThis.fetch;
  else globalThis.fetch = originalFetch;
}

export function networkAttempts() {
  return attempts;
}
