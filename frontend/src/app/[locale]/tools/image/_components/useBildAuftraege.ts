"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { backendApi, downloadJobAsBlob, parseDetail, pollJob } from "@/lib/api";

export interface BildErgebnis {
  jobUuid: string;
  url: string;
  blob: Blob;
  filename: string;
  beschreibung?: string;
  modellPrompt?: string;
}

interface BildMeta {
  beschreibung?: string;
  modell_prompt?: string;
}

/** The description the backend stored with a picture, the same the history shows. */
export function ausMeta(meta: unknown): Pick<BildErgebnis, "beschreibung" | "modellPrompt"> {
  const m = (meta ?? {}) as BildMeta;
  return { beschreibung: m.beschreibung, modellPrompt: m.modell_prompt };
}

/** Sends one form, follows every job it created, and shows each picture as soon as it is ready. */
export function useBildAuftraege(spinner: string, laenger: string, unbekannt: string) {
  const [laeuft, setLaeuft] = useState(false);
  const [label, setLabel] = useState(spinner);
  const [fehler, setFehler] = useState("");
  const [ergebnisse, setErgebnisse] = useState<BildErgebnis[]>([]);
  const [teilweise, setTeilweise] = useState<{ gestartet: number; gewuenscht: number } | null>(null);
  const urls = useRef<string[]>([]);

  const aufraeumen = useCallback(() => {
    urls.current.forEach((u) => URL.revokeObjectURL(u));
    urls.current = [];
  }, []);
  useEffect(() => aufraeumen, [aufraeumen]);

  const zuruecksetzen = useCallback(() => {
    aufraeumen();
    setErgebnisse([]);
    setFehler("");
    setTeilweise(null);
  }, [aufraeumen]);

  const starte = useCallback(async (pfad: string, formular: FormData) => {
    setLaeuft(true);
    setLabel(spinner);
    zuruecksetzen();
    try {
      const antwort = await backendApi.fetch(pfad, { method: "POST", body: formular });
      if (!antwort.ok) {
        const err = await antwort.json().catch(() => ({ detail: unbekannt }));
        throw new Error(parseDetail(err.detail, unbekannt));
      }
      const daten = await antwort.json();
      const jobs: string[] = daten.job_uuids ?? [daten.job_uuid];
      if (daten.teilweise) setTeilweise({ gestartet: jobs.length, gewuenscht: Number(formular.get("varianten")) });
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const ausgang = await Promise.allSettled(jobs.map(async (jobUuid) => {
        const status = await pollJob(jobUuid, undefined, 3000, undefined, () => setLabel(laenger), 60_000);
        const { blob, filename } = await downloadJobAsBlob(jobUuid);
        const url = URL.createObjectURL(blob);
        urls.current.push(url);
        setErgebnisse((alt) => [...alt, { jobUuid, url, blob, filename, ...ausMeta(status.meta) }]);
      }));
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const gescheitert = ausgang.find((a): a is PromiseRejectedResult => a.status === "rejected");
      if (gescheitert) {
        setFehler(gescheitert.reason instanceof Error ? gescheitert.reason.message : unbekannt);
      }
    } catch (err) {
      setFehler(err instanceof Error ? err.message : unbekannt);
    } finally {
      setLaeuft(false);
    }
  }, [spinner, laenger, unbekannt, zuruecksetzen]);

  return { laeuft, label, fehler, setFehler, ergebnisse, starte, teilweise, zuruecksetzen };
}
