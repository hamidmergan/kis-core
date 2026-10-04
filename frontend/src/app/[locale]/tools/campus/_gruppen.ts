import { toMs } from "@/lib/format";
import type { CampusChatEintrag } from "./_types";

export type GruppenKey = "heute" | "woche" | "aelter";

const TAG_MS = 24 * 60 * 60 * 1000;

/** Chats by age of their last activity: today, the last seven days, older. */
export function gruppiere(
  chats: CampusChatEintrag[],
  now: Date = new Date(),
): Record<GruppenKey, CampusChatEintrag[]> {
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const heuteAb = start.getTime();
  const wocheAb = heuteAb - 6 * TAG_MS;
  const out: Record<GruppenKey, CampusChatEintrag[]> = { heute: [], woche: [], aelter: [] };
  for (const chat of chats) {
    const ms = toMs(chat.updated_at);
    if (ms >= heuteAb) out.heute.push(chat);
    else if (ms >= wocheAb) out.woche.push(chat);
    else out.aelter.push(chat);
  }
  return out;
}
