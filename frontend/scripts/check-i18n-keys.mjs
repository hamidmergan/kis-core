#!/usr/bin/env node
// Verify that all locale message files share the same key set.
// Run before commits or in CI; exits non-zero on any divergence.

import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const messagesDir = join(__dirname, "..", "messages");

function flattenKeys(obj, prefix = "") {
  const keys = new Set();
  for (const [k, v] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      for (const sub of flattenKeys(v, full)) keys.add(sub);
    } else {
      keys.add(full);
    }
  }
  return keys;
}

const files = readdirSync(messagesDir).filter((f) => f.endsWith(".json"));
if (files.length < 2) {
  console.error(`Need at least 2 locale files in ${messagesDir}, found ${files.length}.`);
  process.exit(1);
}

const keysByLocale = {};
for (const f of files) {
  const content = JSON.parse(readFileSync(join(messagesDir, f), "utf8"));
  keysByLocale[f] = flattenKeys(content);
}

const [reference, ...rest] = files;
const refKeys = keysByLocale[reference];
let hasError = false;

for (const f of rest) {
  const keys = keysByLocale[f];
  const missing = [...refKeys].filter((k) => !keys.has(k));
  const extra = [...keys].filter((k) => !refKeys.has(k));
  if (missing.length || extra.length) {
    hasError = true;
    console.error(`\n[${f}] vs [${reference}]`);
    if (missing.length) {
      console.error(`  Missing in ${f}:`);
      for (const k of missing) console.error(`    - ${k}`);
    }
    if (extra.length) {
      console.error(`  Extra in ${f}:`);
      for (const k of extra) console.error(`    + ${k}`);
    }
  }
}

if (hasError) {
  console.error(`\ni18n key parity FAILED. Add the missing keys (with translations) to fix.`);
  process.exit(1);
}

console.log(`i18n key parity OK across ${files.length} locales (${refKeys.size} keys).`);
