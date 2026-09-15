/** The numbers a tool records during the run, for admins only. */
export type JobStats = Record<string, Record<string, unknown>>;

/** Screencast and podcast phases in one order, a job only ever carries its own. */
const REIHENFOLGE = [
  "material",
  "uebersetzung",
  "skript",
  "skripte",
  "bilder",
  "vertonung",
  "clips",
  "untertitel",
  "montage",
  "zusammenfuegen",
];

export interface Phasenzeile {
  phase: string;
  dauerS: number | null;
  fehler: string | null;
  felder: { schluessel: string; wert: string | number | boolean }[];
}

function istLeer(wert: unknown): boolean {
  return wert === null || wert === undefined || wert === "";
}

export function phasenzeilen(stats: JobStats | undefined | null): Phasenzeile[] {
  if (!stats) return [];
  const bekannt = REIHENFOLGE.filter((p) => p in stats);
  const rest = Object.keys(stats).filter((p) => !REIHENFOLGE.includes(p));
  return [...bekannt, ...rest].map((phase) => {
    const eintrag = stats[phase] ?? {};
    const dauer = eintrag.dauer_s;
    const fehler = eintrag.fehler;
    return {
      phase,
      dauerS: typeof dauer === "number" ? dauer : null,
      fehler: typeof fehler === "string" ? fehler : null,
      felder: Object.entries(eintrag)
        .filter(([k, v]) => k !== "dauer_s" && k !== "fehler" && !istLeer(v))
        .map(([schluessel, wert]) => ({ schluessel, wert: wert as string | number | boolean })),
    };
  });
}

export function gesamtdauerS(stats: JobStats | undefined | null): number | null {
  if (!stats) return null;
  const dauern = Object.values(stats)
    .map((e) => e?.dauer_s)
    .filter((d): d is number => typeof d === "number");
  if (dauern.length === 0) return null;
  return dauern.reduce((a, b) => a + b, 0);
}

/** A raw value from the meta.json, made readable. */
export function wertText(
  schluessel: string,
  wert: string | number | boolean,
  locale: string,
  woerter: { ja: string; nein: string },
): string {
  if (typeof wert === "boolean") return wert ? woerter.ja : woerter.nein;
  const tag = locale === "en" ? "en-GB" : "de-DE";
  if (schluessel.endsWith("_bytes") && typeof wert === "number") {
    return `${(wert / 1048576).toLocaleString(tag, {
      minimumFractionDigits: 1, maximumFractionDigits: 1,
    })} MB`;
  }
  if (typeof wert === "number") return wert.toLocaleString(tag);
  return String(wert);
}
