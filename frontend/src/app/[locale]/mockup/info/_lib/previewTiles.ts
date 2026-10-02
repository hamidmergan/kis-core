import type { EventBlock, EventTile } from "../../_lib/types";

type Template = Omit<EventTile, "id">;

/** Stand-in tiles for the preview, one per target kind, the admin writes the real ones. */
export const PREVIEW_TILES: Template[] = [
  {
    icon: "star",
    title: { de: "Stempelkarte", en: "Stamp card" },
    body: { de: "Besuche alle Stände und sammle Stempel.", en: "Visit all stands and collect stamps." },
    button: { de: "Karte öffnen", en: "Open card" },
    target: { kind: "stamp" },
  },
  {
    icon: "info",
    title: { de: "Über das Projekt", en: "About the project" },
    body: { de: "Was KIS ist und wer es nutzen kann.", en: "What KIS is and who can use it." },
    button: { de: "Zur Info-Seite", en: "Open info page" },
    target: { kind: "info" },
  },
  {
    icon: "lightbulb",
    title: { de: "Häufige Fragen", en: "Frequently asked questions" },
    body: { de: "Antworten zu Konto, Daten und Pilot.", en: "Answers about account, data and the pilot." },
    button: { de: "Zu den Fragen", en: "To the questions" },
    target: { kind: "internal", path: "/faq" },
  },
  {
    icon: "francis",
    title: { de: "Demozugang", en: "Demo access" },
    body: { de: "Mit einem Klick in KIS und selbst ausprobieren.", en: "One click into KIS to try it yourself." },
    button: { de: "Ausprobieren", en: "Try it" },
    target: { kind: "directLogin", accessCode: "KIS-DEMO-0000" },
  },
];

function uniqueId(base: string, used: Set<string>): string {
  let id = base;
  for (let n = 2; used.has(id); n++) id = `${base}-${n}`;
  used.add(id);
  return id;
}

/** Cuts from the end or fills with stand-in tiles, kinds not yet present come first. */
export function withTileCount(block: EventBlock, count: number): EventBlock {
  const tiles = block.tiles.slice(0, count);
  const used = new Set(tiles.map((tile) => tile.id));
  const missing = PREVIEW_TILES.filter((tpl) => !tiles.some((tile) => tile.target.kind === tpl.target.kind));
  const pool = [...missing, ...PREVIEW_TILES];
  for (let i = 0; tiles.length < count; i++) {
    const tpl = pool[i % pool.length];
    tiles.push({ ...tpl, id: uniqueId(tpl.target.kind, used) });
  }
  return { ...block, tiles };
}
