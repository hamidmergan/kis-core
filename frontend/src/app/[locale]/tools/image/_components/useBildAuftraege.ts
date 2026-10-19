"use client";

import { useCallback, useRef, useState } from "react";
import { backendApi, downloadJobAsBlob, parseDetail, pollJob } from "@/lib/api";
import { cancelJob } from "@/components/jobs/JobCancelButton";

/** What a picture was made with, as far as the backend stored it. */
export interface BildAngaben {
  stil?: string;
  format?: string;
  qualitaet?: string;
  groesse?: string;
}

/** One answer job about a picture, its heading is the task or the question. */
export interface Beschreibung {
  jobUuid: string;
  titel: string;
}

/** One picture of the page: a created or edited one from a job, or an own upload without a job. */
export interface BildErgebnis {
  key: string;
  jobUuid?: string;
  url: string;
  blob: Blob;
  filename: string;
  bearbeitet?: boolean;
  beschreibung?: string;
  modellPrompt?: string;
  angaben?: BildAngaben;
  /** The file name of the kept source of an edit, loaded only when the picture is shown. */
  vorlage?: string;
  vorlageUrl?: string;
  /** The answers about this picture, oldest first. */
  beschreibungen?: Beschreibung[];
}

interface BildMeta extends BildAngaben {
  beschreibung?: string;
  modell_prompt?: string;
  vorlage?: string;
}

/** The prompt and settings the backend stored with a picture, the same the strip shows. */
export function ausMeta(meta: unknown): Pick<BildErgebnis, "beschreibung" | "modellPrompt" | "angaben" | "vorlage"> {
  const m = (meta ?? {}) as BildMeta;
  return {
    beschreibung: m.beschreibung,
    modellPrompt: m.modell_prompt,
    angaben: { stil: m.stil, format: m.format, qualitaet: m.qualitaet, groesse: m.groesse },
    vorlage: m.vorlage,
  };
}

/** Sends one form, follows every job it created, and hands over each picture as soon as it is ready. */
export function useBildAuftraege(spinner: string, laenger: string, unbekannt: string) {
  const [laeuft, setLaeuft] = useState(false);
  const [label, setLabel] = useState(spinner);
  const [fehler, setFehler] = useState("");
  const [teilweise, setTeilweise] = useState<{ gestartet: number; gewuenscht: number } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const jobsRef = useRef<string[]>([]);

  const starte = useCallback(async (pfad: string, formular: FormData, onBild: (bild: BildErgebnis, erstes: boolean) => void) => {
    setLaeuft(true);
    setLabel(spinner);
    setFehler("");
    setTeilweise(null);
    const controller = new AbortController();
    abortRef.current = controller;
    jobsRef.current = [];
    try {
      const antwort = await backendApi.fetch(pfad, { method: "POST", body: formular });
      if (!antwort.ok) {
        const err = await antwort.json().catch(() => ({ detail: unbekannt }));
        throw new Error(parseDetail(err.detail, unbekannt));
      }
      const daten = await antwort.json();
      const jobs: string[] = daten.job_uuids ?? [daten.job_uuid];
      // A cancel during the upload stops the jobs as soon as their ids are known.
      if (controller.signal.aborted) {
        jobs.forEach(cancelJob);
        return;
      }
      jobsRef.current = jobs;
      if (daten.teilweise) setTeilweise({ gestartet: jobs.length, gewuenscht: Number(formular.get("varianten")) });
      window.dispatchEvent(new Event("kis-jobs-changed"));
      let erstes = true;
      const ausgang = await Promise.allSettled(jobs.map(async (jobUuid) => {
        const status = await pollJob(jobUuid, undefined, 3000, controller.signal, () => setLabel(laenger), 60_000);
        const { blob, filename } = await downloadJobAsBlob(jobUuid);
        onBild({ key: jobUuid, jobUuid, url: URL.createObjectURL(blob), blob, filename, ...ausMeta(status.meta) }, erstes);
        erstes = false;
      }));
      window.dispatchEvent(new Event("kis-jobs-changed"));
      if (controller.signal.aborted) return;
      const gescheitert = ausgang.find((a): a is PromiseRejectedResult => a.status === "rejected");
      if (gescheitert) {
        setFehler(gescheitert.reason instanceof Error ? gescheitert.reason.message : unbekannt);
      }
    } catch (err) {
      if (!controller.signal.aborted) setFehler(err instanceof Error ? err.message : unbekannt);
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setLaeuft(false);
      }
    }
  }, [spinner, laenger, unbekannt]);

  const abbrechen = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    jobsRef.current.forEach(cancelJob);
    jobsRef.current = [];
    setLaeuft(false);
    setLabel(spinner);
  }, [spinner]);

  return { laeuft, label, fehler, setFehler, starte, abbrechen, teilweise };
}
