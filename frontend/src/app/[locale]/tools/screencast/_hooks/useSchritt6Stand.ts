"use client";

import { useEffect, useState } from "react";
import type { VertonterStand } from "../_utils";

export interface GespeicherteEinstellungen {
  provider_id: number;
  voice_id: string;
  voice_label: string;
  target_lang: string;
  speed: number;
  slide_pause: number;
  dpi: number;
  subtitles: boolean;
  video_folien: number[] | null;
  neu_vertonen: number[];
}

interface Antwort {
  einstellungen: GespeicherteEinstellungen | null;
  stand: VertonterStand | null;
  hat_ton: boolean[];
}

/** Fetches on every entry to step 6 what the view needs for its preselection. */
export function useSchritt6Stand(jobUuid: string, aktiv: boolean) {
  const [geladen, setGeladen] = useState(false);
  const [einstellungen, setEinstellungen] = useState<GespeicherteEinstellungen | null>(null);
  const [stand, setStand] = useState<VertonterStand | null>(null);
  const [hatTon, setHatTon] = useState<boolean[]>([]);

  useEffect(() => {
    if (!jobUuid || !aktiv) return;
    let abgebrochen = false;
    setGeladen(false);
    fetch(`/api/screencast/${jobUuid}/vertonungs-stand`, { credentials: "include" })
      .then((r) => (r.ok ? (r.json() as Promise<Antwort>) : null))
      .then((daten) => {
        if (abgebrochen || !daten) return;
        setEinstellungen(daten.einstellungen);
        setStand(daten.stand);
        setHatTon(daten.hat_ton ?? []);
      })
      .catch(() => {})
      .finally(() => { if (!abgebrochen) setGeladen(true); });
    return () => { abgebrochen = true; };
  }, [jobUuid, aktiv]);

  return { geladen, einstellungen, stand, hatTon };
}
