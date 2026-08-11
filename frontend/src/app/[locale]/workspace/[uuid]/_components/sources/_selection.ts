import type { Source } from "../../_types";

/** Eine Quelle ist erst waehlbar, wenn das Lesen fertig ist: Status "ready" und
 *  kein Fortschritt mehr. Vorher bekaeme der Chat von ihr leeren Zusammenhang. */
export const isFullyReady = (s: Source) => s.status === "ready" && !s.progress;

export type GroupState = "none" | "some" | "all";

/** Zustand eines Gruppen-Hakens, abgeleitet aus den Haken der Dateien darin.
 *
 *  Drei Zustaende, weil zwei nicht reichen: bei "some" muss zu sehen sein, dass
 *  die Gruppe angefasst wurde, ohne vollstaendig zu sein.
 *
 *  Nicht fertige Dateien zaehlen nirgends mit. Sonst blieben Gruppen, in denen
 *  gerade etwas indiziert wird, dauerhaft auf "some" stehen.
 */
export function groupState(list: Source[], selected: string[]): GroupState {
  const ready = list.filter(isFullyReady);
  const picked = ready.filter((s) => selected.includes(s.uuid)).length;
  if (ready.length === 0 || picked === 0) return "none";
  return picked === ready.length ? "all" : "some";
}

/** Welche Dateien ein Klick auf den Gruppen-Haken umschaltet.
 *
 *  Vollstaendig gewaehlt heisst abwaehlen, alles andere heisst auswaehlen. Der
 *  Aufrufer schaltet die zurueckgegebenen uuids einzeln um, damit die Auswahl
 *  an einer Stelle gefuehrt wird.
 */
export function toggleGroupTargets(list: Source[], selected: string[]): string[] {
  const ready = list.filter(isFullyReady);
  if (ready.length === 0) return [];
  const allPicked = ready.every((s) => selected.includes(s.uuid));
  return ready
    .filter((s) => (allPicked ? selected.includes(s.uuid) : !selected.includes(s.uuid)))
    .map((s) => s.uuid);
}
