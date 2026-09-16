"use client";

import { useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useDemoWorkspaces } from "./useDemoWorkspaces";
import { waehleRundgangModul } from "./rundgangModul";

/** Joins every demo course, then starts the guided tour in the one it runs in. */
export function useTourStart(enabled = true) {
  const router = useRouter();
  const { items, join } = useDemoWorkspaces(enabled);
  const [busy, setBusy] = useState(false);
  const kurs = waehleRundgangModul(items);

  const start = async () => {
    if (!kurs || busy) return;
    setBusy(true);
    // Everything the demo account offers, not only the course the tour runs in.
    if (items.some((m) => !m.owned && !m.joined)) await join(null);
    // No mark on start: only the last step or the card's hide button takes the invitation away.
    router.push(`/workspace/${kurs.uuid}?tour=1`);
    setBusy(false);
  };

  return { available: !!kurs, busy, start };
}
