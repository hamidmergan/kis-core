"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { backendApi, downloadJobAsBlob } from "@/lib/api";
import { ausMeta, type BildErgebnis, type Beschreibung } from "./useBildAuftraege";

interface Eintrag {
  job_uuid: string;
  tool: string;
  has_download: boolean;
  original_filename?: string;
  meta?: Record<string, unknown> | null;
}

interface AnalyseMeta {
  quelle?: string;
  titel?: string;
  dateiname?: string;
}

const ANZAHL = 12;
const EIGEN = "eigen-";
const BILD_TOOLS = new Set(["image_generate", "image_edit"]);

// Local answers that the job list does not know yet stay, the list adds the rest.
function vereinen(alt: Beschreibung[] = [], neu: Beschreibung[] = []): Beschreibung[] {
  const bekannt = new Set(neu.map((b) => b.jobUuid));
  return [...neu, ...alt.filter((b) => !bekannt.has(b.jobUuid))];
}

// Every picture owns its own addresses, the source of an edit included, so freeing one never breaks another.
function freigeben(bild: BildErgebnis) {
  URL.revokeObjectURL(bild.url);
  if (bild.vorlageUrl) URL.revokeObjectURL(bild.vorlageUrl);
}

/** All pictures of the page: the last created, edited and described ones, new results, and own uploads of this visit. */
export function useBilder() {
  const [bilder, setBilder] = useState<BildErgebnis[]>([]);
  const [eigene, setEigene] = useState<BildErgebnis[]>([]);
  const geladen = useRef(new Map<string, BildErgebnis>());
  // Results that arrived before the job list knows them, they stay in front until it does.
  const frisch = useRef(new Set<string>());
  const hochgeladen = useRef(0);
  const eigeneUrls = useRef<string[]>([]);
  const vorlageVersucht = useRef(new Set<string>());
  // Answers about an upload of this visit, that upload already shows them, the list must not add it twice.
  const uebernommen = useRef(new Set<string>());
  const wurzeln = useRef(new Map<string, string>());

  const laden = useCallback(async () => {
    try {
      const antwort = await backendApi.fetch(`/jobs/my?tool_filter=image&limit=40`);
      if (!antwort.ok) return;
      const { jobs } = (await antwort.json()) as { jobs: Eintrag[] };
      const fertig = jobs.filter((j) => j.has_download);
      const bildJobs = new Set(fertig.filter((j) => BILD_TOOLS.has(j.tool)).map((j) => j.job_uuid));
      // Answers belong to the picture they were about, answers about an upload to the first answer of that upload.
      const gruppen = new Map<string, Eintrag[]>();
      const schluessel: string[] = [];
      for (const j of fertig) {
        if (BILD_TOOLS.has(j.tool)) schluessel.push(j.job_uuid);
        if (j.tool !== "image_analyze") continue;
        const wurzel = (j.meta as AnalyseMeta | null)?.quelle || j.job_uuid;
        if (!gruppen.has(wurzel)) {
          gruppen.set(wurzel, []);
          if (!bildJobs.has(wurzel) && !uebernommen.current.has(wurzel)) schluessel.push(wurzel);
        }
        gruppen.get(wurzel)!.push(j);
      }
      const antworten = (key: string): Beschreibung[] => [...(gruppen.get(key) ?? [])].reverse()
        .map((j) => ({ jobUuid: j.job_uuid, titel: (j.meta as AnalyseMeta | null)?.titel ?? "" }));
      const passend = schluessel.slice(0, ANZAHL);
      const liste = await Promise.all(passend.map(async (key) => {
        const bekannt = geladen.current.get(key);
        if (bekannt) {
          const aktuell = { ...bekannt, beschreibungen: vereinen(bekannt.beschreibungen, antworten(key)) };
          geladen.current.set(key, aktuell);
          return aktuell;
        }
        const job = fertig.find((j) => j.job_uuid === key);
        let bild: BildErgebnis;
        if (job && BILD_TOOLS.has(job.tool)) {
          const { blob, filename } = await downloadJobAsBlob(key);
          bild = { key, jobUuid: key, url: URL.createObjectURL(blob), blob, filename,
            bearbeitet: job.tool === "image_edit", ...ausMeta(job.meta), beschreibungen: antworten(key) };
        } else {
          // A described upload, its picture lies with its oldest answer.
          const erste = [...gruppen.get(key)!].reverse()[0];
          const antwort = await backendApi.fetch(`/image/${erste.job_uuid}/vorlage`);
          if (!antwort.ok) return null;
          const blob = await antwort.blob();
          const filename = (erste.meta as AnalyseMeta | null)?.dateiname ?? erste.original_filename ?? "bild";
          bild = { key, url: URL.createObjectURL(blob), blob, filename, beschreibungen: antworten(key) };
        }
        // A result can arrive while this download runs, then that one wins with its source.
        const inzwischen = geladen.current.get(key);
        if (inzwischen) {
          URL.revokeObjectURL(bild.url);
          return inzwischen;
        }
        geladen.current.set(key, bild);
        return bild;
      })).then((alle) => alle.filter((b): b is BildErgebnis => !!b));
      passend.forEach((key) => frisch.current.delete(key));
      const vorne = [...frisch.current].map((k) => geladen.current.get(k)).filter((b): b is BildErgebnis => !!b);
      setBilder([...vorne, ...liste]);
    } catch {
      // Without the history the tool still works, the strip simply stays as it was.
    }
  }, []);

  useEffect(() => {
    void laden();
    const neu = () => { void laden(); };
    window.addEventListener("kis-jobs-changed", neu);
    const karte = geladen.current;
    const urls = eigeneUrls.current;
    return () => {
      window.removeEventListener("kis-jobs-changed", neu);
      karte.forEach(freigeben);
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [laden]);

  /** A fresh result goes to the front right away, the next load of the list keeps it there. */
  const aufnehmen = useCallback((bild: BildErgebnis) => {
    geladen.current.set(bild.key, bild);
    frisch.current.add(bild.key);
    setBilder((alt) => [bild, ...alt.filter((b) => b.key !== bild.key)]);
  }, []);

  /** An own picture for editing or describing, it has no job and lives only on this visit. */
  const hochladen = useCallback((datei: File): string => {
    const key = `${EIGEN}${++hochgeladen.current}`;
    const url = URL.createObjectURL(datei);
    eigeneUrls.current.push(url);
    setEigene((alt) => [{ key, url, blob: datei, filename: datei.name }, ...alt]);
    return key;
  }, []);

  /** Deletes the jobs behind a picture and its answers, the picture leaves the strip only when that worked. */
  const loeschen = useCallback(async (bild: BildErgebnis) => {
    const uuids = [bild.jobUuid, ...(bild.beschreibungen ?? []).map((b) => b.jobUuid)].filter((u): u is string => !!u);
    if (!uuids.length) return;
    const antworten = await Promise.all(uuids.map((u) => backendApi.fetch(`/jobs/${u}`, { method: "DELETE" })));
    if (antworten.some((a) => !a.ok && a.status !== 404)) throw new Error(String(antworten.find((a) => !a.ok)?.status));
    setEigene((alt) => alt.filter((b) => b.key !== bild.key));
    const eintrag = geladen.current.get(bild.key);
    geladen.current.delete(bild.key);
    frisch.current.delete(bild.key);
    setBilder((alt) => alt.filter((b) => b.key !== bild.key));
    if (eintrag) freigeben(eintrag);
    window.dispatchEvent(new Event("kis-jobs-changed"));
  }, []);

  /** The kept source of an older edit, fetched once when the picture is first shown. */
  const vorlageLaden = useCallback(async (bild: BildErgebnis) => {
    if (!bild.jobUuid || !bild.vorlage || bild.vorlageUrl || vorlageVersucht.current.has(bild.key)) return;
    vorlageVersucht.current.add(bild.key);
    try {
      const antwort = await backendApi.fetch(`/image/${bild.jobUuid}/vorlage`);
      if (!antwort.ok) return;
      const url = URL.createObjectURL(await antwort.blob());
      const eintrag = geladen.current.get(bild.key);
      if (eintrag) eintrag.vorlageUrl = url;
      setBilder((alt) => alt.map((b) => (b.key === bild.key ? { ...b, vorlageUrl: url } : b)));
    } catch {
      // Without its source the picture shows alone, as before.
    }
  }, []);

  /** A fresh answer about a picture, the strip marks the picture as described right away. */
  const beschrieben = useCallback((key: string, neu: Beschreibung) => {
    const dazu = (b: BildErgebnis) => (b.key === key ? { ...b, beschreibungen: vereinen([neu], b.beschreibungen) } : b);
    const eintrag = geladen.current.get(key);
    if (eintrag) geladen.current.set(key, dazu(eintrag));
    setBilder((alt) => alt.map(dazu));
    setEigene((alt) => alt.map(dazu));
  }, []);

  /** A started answer, the first one about an upload names that upload in the job list from now on. */
  const vormerken = useCallback((key: string, jobUuid: string) => {
    if (!key.startsWith(EIGEN) || wurzeln.current.has(key)) return;
    wurzeln.current.set(key, jobUuid);
    uebernommen.current.add(jobUuid);
  }, []);

  return { alle: [...eigene, ...bilder], aufnehmen, hochladen, loeschen, vorlageLaden, beschrieben, vormerken };
}
