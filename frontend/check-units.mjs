#!/usr/bin/env node
// Verify that no font size is hard-coded in pixels.
//
// Why: a single text-[11px] pins one element to a value nobody can find again.
// Change the scale in globals.css and that element stays put, and nobody
// notices for months. Named sizes exist for every value the app uses:
// text-3xs (10px) … text-3xl (30px), see the @theme block in globals.css.
// They also follow the browser font size setting, fixed pixels do not.
//
// Scope is deliberately font sizes only. Fixed pixels are correct for border
// widths and corner radii, and a rule that needs constant exceptions gets
// ignored instead of followed.
//
// Run before commits or in CI; exits non-zero on any finding.

import { readFileSync, readdirSync } from "node:fs";
import { join, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = join(__dirname, "src");

// Next.js Bildrouten (ImageResponse/satori) rendern in eine PNG-Datei, nicht
// ins Browser-DOM. Dort gibt es keine Wurzel-Schriftgroesse, rem waere falsch.
const EXEMPT = /(^|\/)(icon|apple-icon|opengraph-image|twitter-image)\.tsx$/;

const RULES = [
  {
    // text-[11px], text-[11.5px] — Tailwind arbitrary font size in pixels
    pattern: /\btext-\[[0-9.]+px\]/g,
    hint: "benannte Groesse nutzen: text-3xs 10px, text-2xs 11px, text-xs 12px, text-sm 14px, text-base 16px, text-lg 18px",
  },
  {
    // style={{ fontSize: 14 }} — pixel number in a style object.
    // fontSize="14" as a JSX attribute is the SVG form and stays allowed:
    // there the number is a user-space unit, not a CSS pixel.
    pattern: /\bfontSize:\s*[0-9]/g,
    hint: 'in rem angeben, z.B. fontSize: "0.875rem"',
  },
];

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (/\.(tsx|ts)$/.test(entry.name)) out.push(full);
  }
  return out;
}

const findings = [];
for (const file of walk(srcDir)) {
  if (EXEMPT.test(file)) continue;
  const lines = readFileSync(file, "utf8").split("\n");
  lines.forEach((line, i) => {
    for (const { pattern, hint } of RULES) {
      for (const match of line.matchAll(pattern)) {
        findings.push({
          file: relative(__dirname, file),
          line: i + 1,
          match: match[0],
          hint,
        });
      }
    }
  });
}

if (findings.length > 0) {
  console.error(`Feste Pixel-Schriftgroessen gefunden (${findings.length}):\n`);
  for (const f of findings) {
    console.error(`  ${f.file}:${f.line}  ${f.match}`);
    console.error(`    -> ${f.hint}`);
  }
  console.error(
    "\nGrund: Groessen gehoeren in den @theme-Block, nicht verstreut in die Komponenten.",
  );
  console.error("Feste Pixel folgen ausserdem nicht der Schriftgroesse des Browsers.");
  process.exit(1);
}

console.log("check:units OK — keine festen Pixel-Schriftgroessen in src/");
