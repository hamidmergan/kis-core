"use client";

import { useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useDemoWorkspaces } from "./useDemoWorkspaces";

/** Finds the demo course and starts the guided tour in it, joining first if needed. */
export function useTourStart(enabled = true) {
  const router = useRouter();
  const { items, join } = useDemoWorkspaces(enabled);
  const [busy, setBusy] = useState(false);
  const kurs = items.find((m) => !m.owned);

  const start = async () => {
    if (!kurs || busy) return;
    setBusy(true);
    if (!kurs.joined) await join(kurs.uuid);
    // No mark on start: only the last step or the card's hide button takes the invitation away.
    router.push(`/workspace/${kurs.uuid}?tour=1`);
    setBusy(false);
  };

  return { available: !!kurs, busy, start };
}
