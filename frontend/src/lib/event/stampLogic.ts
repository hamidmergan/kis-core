import type { Card, Station } from "@/lib/event/types";

type Stand = Pick<Station, "id">;

/** Stamps for stations the admin removed in the meantime do not count. */
export function stampedIds(card: Card, stations: Stand[]): string[] {
  return stations.filter((s) => s.id in card.stamped).map((s) => s.id);
}

export function openStations<T extends Stand>(card: Card, stations: T[]): T[] {
  return stations.filter((s) => !(s.id in card.stamped));
}

export function isComplete(card: Card, stations: Stand[]): boolean {
  return stations.length > 0 && openStations(card, stations).length === 0;
}

/** The next open station after the one just stamped, wrapping around to the start. */
export function suggestNext<T extends Stand>(card: Card, stations: T[], afterId?: string | null): T | null {
  const open = openStations(card, stations);
  if (open.length === 0) return null;
  const from = afterId ? stations.findIndex((s) => s.id === afterId) : -1;
  return open.find((s) => stations.indexOf(s) > from) ?? open[0];
}
