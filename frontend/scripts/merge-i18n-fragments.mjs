#!/usr/bin/env node
/**
 * Deep-merges all frontend/messages/_partial/*-{de,en}.json into
 * frontend/messages/{de,en}.json. Fragment files take precedence on key conflict.
 *
 * Usage: node frontend/scripts/merge-i18n-fragments.mjs
 *   --dry        Print resulting merged JSON to stdout, do not write
 *   --remove     Delete the _partial directory after a successful merge
 */

import { readdirSync, readFileSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { resolve, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const messagesDir = resolve(__dirname, "..", "messages");
const partialDir = join(messagesDir, "_partial");

const args = new Set(process.argv.slice(2));
const dryRun = args.has("--dry");
const removeAfter = args.has("--remove");

function isObject(v) {
  return v && typeof v === "object" && !Array.isArray(v);
}

function deepMerge(a, b) {
  if (!isObject(a) || !isObject(b)) return b;
  const out = { ...a };
  for (const key of Object.keys(b)) {
    out[key] = isObject(a[key]) && isObject(b[key]) ? deepMerge(a[key], b[key]) : b[key];
  }
  return out;
}

function loadJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function mergeForLocale(locale) {
  const target = join(messagesDir, `${locale}.json`);
  let base = existsSync(target) ? loadJson(target) : {};

  const fragments = readdirSync(partialDir)
    .filter((f) => f.endsWith(`-${locale}.json`))
    .sort();

  if (fragments.length === 0) {
    console.log(`[${locale}] no fragments found`);
    return base;
  }

  for (const f of fragments) {
    const frag = loadJson(join(partialDir, f));
    base = deepMerge(base, frag);
    console.log(`[${locale}] merged ${f}`);
  }

  if (!dryRun) {
    writeFileSync(target, JSON.stringify(base, null, 2) + "\n", "utf8");
    console.log(`[${locale}] wrote ${target}`);
  }
  return base;
}

if (!existsSync(partialDir)) {
  console.error(`No _partial directory at ${partialDir}`);
  process.exit(1);
}

mergeForLocale("de");
mergeForLocale("en");

if (removeAfter && !dryRun) {
  rmSync(partialDir, { recursive: true, force: true });
  console.log(`removed ${partialDir}`);
}
