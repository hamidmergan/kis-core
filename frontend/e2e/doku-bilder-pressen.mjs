// Presst die Doku-Bilder auf etwa ein Drittel, ohne sichtbaren Verlust.
// Nach jedem Lauf von doku-bilder.spec.ts einmal ausfuehren: node e2e/doku-bilder-pressen.mjs
// sharp kommt ueber Next mit, steht also nicht in der package.json.
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

const ROOT = "public/doku";
let vorher = 0;
let nachher = 0;

for (const locale of fs.readdirSync(ROOT)) {
  const dir = path.join(ROOT, locale);
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith(".png")) continue;
    const p = path.join(dir, file);
    const alt = fs.statSync(p).size;
    // Screenshots sind Flaechen mit wenig Farben, eine Palette reicht.
    const buf = await sharp(p).png({ palette: true, quality: 90, effort: 10 }).toBuffer();
    if (buf.length < alt) fs.writeFileSync(p, buf);
    const neu = fs.statSync(p).size;
    vorher += alt;
    nachher += neu;
    console.log(`${locale}/${file}: ${(alt / 1024).toFixed(0)} kB -> ${(neu / 1024).toFixed(0)} kB`);
  }
}

console.log(`\nGesamt: ${(vorher / 1024 / 1024).toFixed(1)} MB -> ${(nachher / 1024 / 1024).toFixed(1)} MB`);
