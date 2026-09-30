"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { backendApi, downloadJobAsBlob } from "@/lib/api";
import { ausMeta, type BildErgebnis } from "./useBildAuftraege";

interface Eintrag {
  job_uuid: string;
  tool: string;
  has_download: boolean;
  meta?: Record<string, unknown> | null;
}

const ANZAHL = 12;

// Every picture owns its own addresses, the source of an edit included, so freeing one never breaks another.
function freigeben(bild: BildErgebnis) {
  URL.revokeObjectURL(bild.url);
  if (bild.vorlageUrl) URL.revokeObjectURL(bild.vorlageUrl);
}

/** All pictures of the page: the last created and edited ones, new results, and own uploads of this visit. */
export function useBilder() {
  const [bilder, setBilder] = useState<BildErgebnis[]>([]);
  const [eigene, setEigene] = useState<BildErgebnis[]>([]);
  const geladen = useRef(new Map<string, BildErgebnis>());
  // Results that arrived before the job list knows them, they stay in front until it does.
  const frisch = useRef(new Set<string>());
  const hochgeladen = useRef(0);
  const eigeneUrls = useRef<string[]>([]);
  const vorlageVersucht = useRef(new Set<string>());

  const laden = useCallback(async () => {
    try {
      const antwort = await backendApi.fetch(`/jobs/my?tool_filter=image&limit=40`);
      if (!antwort.ok) return;
      const { jobs } = (await antwort.json()) as { jobs: Eintrag[] };
      const passend = jobs
        .filter((j) => j.has_download && (j.tool === "image_generate" || j.tool === "image_edit"))
        .slice(0, ANZAHL);
      const liste = await Promise.all(passend.map(async (j) => {
        const bekannt = geladen.current.get(j.job_uuid);
        if (bekannt) return bekannt;
        const { blob, filename } = await downloadJobAsBlob(j.job_uuid);
        // A result can arrive while this download runs, then that one wins with its source.
        const inzwischen = geladen.current.get(j.job_uuid);
        if (inzwischen) return inzwischen;
        const bild: BildErgebnis = { key: j.job_uuid, jobUuid: j.job_uuid, url: URL.createObjectURL(blob), blob, filename,
          bearbeitet: j.tool === "image_edit", ...ausMeta(j.meta) };
        geladen.current.set(j.job_uuid, bild);
        return bild;
      }));
      passend.forEach((j) => frisch.current.delete(j.job_uuid));
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
    const key = `eigen-${++hochgeladen.current}`;
    const url = URL.createObjectURL(datei);
    eigeneUrls.current.push(url);
    setEigene((alt) => [{ key, url, blob: datei, filename: datei.name }, ...alt]);
    return key;
  }, []);

  /** Deletes the job behind a picture, the picture leaves the strip only when that worked. */
  const loeschen = useCallback(async (bild: BildErgebnis) => {
    if (!bild.jobUuid) return;
    const antwort = await backendApi.fetch(`/jobs/${bild.jobUuid}`, { method: "DELETE" });
    if (!antwort.ok) throw new Error(String(antwort.status));
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

  return { alle: [...eigene, ...bilder], aufnehmen, hochladen, loeschen, vorlageLaden };
}
