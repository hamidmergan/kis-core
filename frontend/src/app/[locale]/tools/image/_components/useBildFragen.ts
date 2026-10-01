"use client";

import { useCallback, useRef, useState } from "react";
import { backendApi, downloadJobAsBlob, parseDetail, pollJob } from "@/lib/api";
import type { BildErgebnis, Beschreibung } from "./useBildAuftraege";
import type { AUFGABEN } from "../_utils";

export interface Antwort {
  frage: string;
  text: string;
}

interface Frage {
  aufgabe: (typeof AUFGABEN)[number];
  text: string;
  /** The heading of the answer, the task name or the question itself. */
  titel: string;
  sprache: "de" | "en";
  providerId: number | null;
}

/** Answers about pictures, kept per picture, every question adds to the answers of the same one. */
export function useBildFragen(spinner: string, laenger: string, unbekannt: string,
                              onAuftrag: (key: string, jobUuid: string) => void,
                              onAntwort: (key: string, beschreibung: Beschreibung) => void) {
  const [antworten, setAntworten] = useState<Record<string, Antwort[]>>({});
  const [laeuft, setLaeuft] = useState(false);
  const [label, setLabel] = useState(spinner);
  const [fehler, setFehler] = useState("");
  // A further question keeps the language and provider of the question before it.
  const zuletzt = useRef<Pick<Frage, "sprache" | "providerId">>({ sprache: "de", providerId: null });
  const geholt = useRef(new Set<string>());

  const fragen = useCallback(async (bild: BildErgebnis, frage: Frage) => {
    setLaeuft(true);
    setLabel(spinner);
    setFehler("");
    zuletzt.current = { sprache: frage.sprache, providerId: frage.providerId };
    try {
      const formular = new FormData();
      formular.append("image", new File([bild.blob], bild.filename, { type: bild.blob.type || "image/png" }));
      formular.append("aufgabe", frage.aufgabe);
      formular.append("sprache", frage.sprache);
      formular.append("prompt", frage.aufgabe === "frage" ? frage.text : "");
      if (frage.providerId != null) formular.append("provider_id", String(frage.providerId));
      // Links the answer to its picture, an upload to its first answer.
      formular.append("quelle", bild.jobUuid ?? bild.beschreibungen?.[0]?.jobUuid ?? "");
      formular.append("titel", frage.titel);
      const antwort = await backendApi.fetch("/image/analyze", { method: "POST", body: formular });
      if (!antwort.ok) {
        const err = await antwort.json().catch(() => ({ detail: unbekannt }));
        throw new Error(parseDetail(err.detail, unbekannt));
      }
      const daten = await antwort.json();
      onAuftrag(bild.key, daten.job_uuid);
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(daten.job_uuid, undefined, 3000, undefined, () => setLabel(laenger), 60_000);
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const { blob } = await downloadJobAsBlob(daten.job_uuid);
      const eintrag = { frage: frage.titel, text: await blob.text() };
      setAntworten((alt) => ({ ...alt, [bild.key]: [...(alt[bild.key] ?? []), eintrag] }));
      onAntwort(bild.key, { jobUuid: daten.job_uuid, titel: frage.titel });
      return true;
    } catch (err) {
      setFehler(err instanceof Error ? err.message : unbekannt);
      return false;
    } finally {
      setLaeuft(false);
    }
  }, [spinner, laenger, unbekannt, onAuftrag, onAntwort]);

  const nachfragen = useCallback((bild: BildErgebnis, text: string) =>
    fragen(bild, { aufgabe: "frage", text, titel: text, ...zuletzt.current }), [fragen]);

  /** The kept answers of a picture, fetched once when the picture is first shown. */
  const antwortenLaden = useCallback(async (bild: BildErgebnis) => {
    const liste = bild.beschreibungen ?? [];
    // Answers given later on this visit are already shown, so a picture is fetched only once.
    if (geholt.current.has(bild.key)) return;
    geholt.current.add(bild.key);
    if (!liste.length) return;
    try {
      const geladen = await Promise.all(liste.map(async (b) => {
        const { blob } = await downloadJobAsBlob(b.jobUuid);
        return { frage: b.titel, text: await blob.text() };
      }));
      // A question asked in the meantime already shows its answer, the kept ones go in front of it.
      setAntworten((alt) => ({ ...alt, [bild.key]: [...geladen, ...(alt[bild.key] ?? [])] }));
    } catch {
      geholt.current.delete(bild.key);
    }
  }, []);

  return { antworten, laeuft, label, fehler, fragen, nachfragen, antwortenLaden };
}
