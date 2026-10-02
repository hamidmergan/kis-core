import { newUniqueCode } from "../../_lib/masterCode";
import { SEED_CONFIG } from "../../_lib/seed";
import type { MockupCard, Station } from "../../_lib/types";

/** Stamps for stations the admin removed in the meantime do not count. */
export function stampedIds(card: MockupCard, stations: Station[]): string[] {
  return stations.filter((s) => s.id in card.stamped).map((s) => s.id);
}

export function openStations(card: MockupCard, stations: Station[]): Station[] {
  return stations.filter((s) => !(s.id in card.stamped));
}

export function isComplete(card: MockupCard, stations: Station[]): boolean {
  return stations.length > 0 && openStations(card, stations).length === 0;
}

/** The next open station after the one just stamped, wrapping around to the start. */
export function suggestNext(card: MockupCard, stations: Station[], afterId?: string | null): Station | null {
  const open = openStations(card, stations);
  if (open.length === 0) return null;
  const from = afterId ? stations.findIndex((s) => s.id === afterId) : -1;
  return open.find((s) => stations.indexOf(s) > from) ?? open[0];
}

/** Sets completedAt once every station is stamped and clears it again when a new station appears. */
export function syncCompletion(card: MockupCard, stations: Station[], now: number): MockupCard {
  const complete = isComplete(card, stations);
  if (complete && card.completedAt === null) return { ...card, completedAt: now };
  if (!complete && card.completedAt !== null) return { ...card, completedAt: null };
  return card;
}

/** Idempotent, an unknown id or a repeated stamp returns the same card. */
export function stamp(card: MockupCard, stations: Station[], id: string, now: number): MockupCard {
  if (!stations.some((s) => s.id === id) || id in card.stamped) return card;
  return syncCompletion({ ...card, stamped: { ...card.stamped, [id]: now } }, stations, now);
}

function genericStation(n: number, code: string): Station {
  return {
    id: `stand-${n}`,
    code,
    icon: "star",
    name: { de: `Stand ${n}`, en: `Stand ${n}` },
    blurb: { de: "Beispielstand für die Simulation", en: "Sample stand for the simulation" },
    francis: { de: "Hier könnte ein weiterer Stand stehen.", en: "Another stand could be here." },
  };
}

/** Cuts the list or refills it from the seed, then from generic stands with unused ids. */
export function resizeStations(stations: Station[], count: number): Station[] {
  if (count <= stations.length) return stations.slice(0, count);
  const out = [...stations];
  const used = new Set(out.map((s) => s.id));
  for (const s of SEED_CONFIG.stations) {
    if (out.length >= count) break;
    if (!used.has(s.id)) {
      out.push(s);
      used.add(s.id);
    }
  }
  for (let n = 1; out.length < count; n++) {
    const g = genericStation(n, newUniqueCode([SEED_CONFIG.masterCode, ...out.map((s) => s.code)]));
    if (!used.has(g.id)) {
      out.push(g);
      used.add(g.id);
    }
  }
  return out;
}
