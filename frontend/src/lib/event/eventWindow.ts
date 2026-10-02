import type { EventBlock } from "@/lib/event/types";

const berlinDay = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Berlin" });

/** The block shows while it is on and today lies inside from and until, an empty bound is open. */
export function eventActive(block: EventBlock, now: Date = new Date()): boolean {
  if (!block.enabled) return false;
  if (block.ignoreWindow) return true;
  const today = berlinDay.format(now);
  if (block.from && today < block.from) return false;
  if (block.until && today > block.until) return false;
  return true;
}
