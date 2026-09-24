/** Mirrors SOURCES_MAX_TOTAL_CHARS in the backend, the answer of a measurement overrides it. */
export const MAX_MATERIAL_CHARS = 500_000;

export type Messung =
  | { status: "laeuft" }
  | { status: "fertig"; chars: number }
  | { status: "fehler"; message: string };

export interface Bilanz {
  total: number;
  pending: boolean;
  failed: boolean;
  over: boolean;
  ready: boolean;
}

/** Name, size and date together, so a changed file with the same name is counted again. */
export function dateiSchluessel(f: File): string {
  return `${f.name}|${f.size}|${f.lastModified}`;
}

/** What the picked material adds up to, and whether it may start. */
export function bilanz(messungen: (Messung | undefined)[], max: number): Bilanz {
  let total = 0;
  let pending = false;
  let failed = false;
  for (const m of messungen) {
    if (!m || m.status === "laeuft") pending = true;
    else if (m.status === "fehler") failed = true;
    else total += m.chars;
  }
  const over = total > max;
  return { total, pending, failed, over, ready: messungen.length > 0 && !pending && !failed && !over };
}
