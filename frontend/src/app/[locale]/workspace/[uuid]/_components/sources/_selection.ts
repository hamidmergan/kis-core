import type { Source } from "../../_types";

/** A source is only selectable once reading is finished. */
export const isFullyReady = (s: Source) => s.status === "ready" && !s.progress;

export type GroupState = "none" | "some" | "all";

/** Three states of a group checkbox, unfinished files count nowhere unless the caller says otherwise. */
export function groupState(list: Source[], selected: string[], selectable = isFullyReady): GroupState {
  const ready = list.filter(selectable);
  const picked = ready.filter((s) => selected.includes(s.uuid)).length;
  if (ready.length === 0 || picked === 0) return "none";
  return picked === ready.length ? "all" : "some";
}

/** Which files a click on the group checkbox toggles. */
export function toggleGroupTargets(list: Source[], selected: string[], selectable = isFullyReady): string[] {
  const ready = list.filter(selectable);
  if (ready.length === 0) return [];
  const allPicked = ready.every((s) => selected.includes(s.uuid));
  return ready
    .filter((s) => (allPicked ? selected.includes(s.uuid) : !selected.includes(s.uuid)))
    .map((s) => s.uuid);
}
