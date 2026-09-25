// Renders the Phosphor Regular icons the presentation tool may place on cards into
// grey masks, which the build tints in the template's colour.
// Run from the frontend folder: node ../backend/scripts/praesentation_icons.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

// Resolved from the frontend folder, the script itself lives outside its node_modules.
const { chromium } = createRequire(`${process.cwd()}/`)("playwright");

const ZIEL = "../backend/src/features/praesentation/icons";
const GROESSE = 256;
const NAMEN = [
  "atom", "book-open", "books", "brain", "briefcase", "buildings", "calendar", "chalkboard-teacher",
  "chart-bar", "chart-line-up", "chart-pie", "chats", "check-circle", "clipboard-text", "clock", "cloud", "code",
  "cpu", "currency-eur", "database", "desktop", "device-mobile", "dna", "envelope", "eye", "factory", "file-text",
  "flag", "flask", "folder", "gavel", "gear", "globe", "graduation-cap", "handshake", "heart", "heartbeat",
  "hourglass", "house", "image", "info", "key", "leaf", "lightbulb", "lightning", "list-checks", "lock",
  "magnifying-glass", "map-pin", "megaphone", "microphone", "money", "path", "pencil", "puzzle-piece", "recycle",
  "robot", "rocket", "scales", "shield-check", "star", "student", "target", "translate", "tree-structure",
  "trophy", "truck", "users", "user", "video-camera", "warning", "wifi-high", "wrench",
];

const pascal = (n) => n.split("-").map((t) => t[0].toUpperCase() + t.slice(1)).join("");

function pfade(name) {
  const js = readFileSync(`node_modules/@phosphor-icons/react/dist/defs/${pascal(name)}.es.js`, "utf8");
  const regular = js.split('"regular"')[1].split(/\n  \]/)[0];
  return [...regular.matchAll(/d: "([^"]+)"/g)].map((m) => m[1]);
}

const vorhanden = NAMEN.filter((n) => {
  try { pfade(n); return true; } catch { console.warn("fehlt:", n); return false; }
});
mkdirSync(ZIEL, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage();
for (const name of vorhanden) {
  const daten = await page.evaluate(([ds, g]) => {
    const c = document.createElement("canvas");
    c.width = c.height = g;
    const ctx = c.getContext("2d");
    ctx.scale(g / 256, g / 256);
    ctx.fillStyle = "#000";
    for (const d of ds) ctx.fill(new Path2D(d));
    return c.toDataURL("image/png");
  }, [pfade(name), GROESSE]);
  writeFileSync(`${ZIEL}/${name}.png`, Buffer.from(daten.split(",")[1], "base64"));
}
await browser.close();
console.log(vorhanden.length, "Icons");
