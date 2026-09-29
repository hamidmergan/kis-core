"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi, downloadJobAsBlob } from "@/lib/api";
import BeschreibungText from "./BeschreibungText";
import { ausMeta, type BildErgebnis } from "./useBildAuftraege";
import { speichern } from "../_utils";

interface Eintrag {
  job_uuid: string;
  tool: string;
  status: string;
  has_download: boolean;
  original_filename: string;
  meta?: Record<string, unknown> | null;
}

interface Props {
  onBearbeiten: (bild: BildErgebnis) => void;
  onBeschreiben: (bild: BildErgebnis) => void;
}

const ANZAHL = 12;
const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors";

/** The last created and edited pictures of this person, a click picks one for the other tasks. */
export default function Verlauf({ onBearbeiten, onBeschreiben }: Props) {
  const t = useTranslations("tools.image.history");
  const tResult = useTranslations("tools.image.result");
  const [bilder, setBilder] = useState<(BildErgebnis & { name: string })[]>([]);
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  const geladen = useRef(new Map<string, BildErgebnis>());

  const laden = useCallback(async () => {
    try {
      const antwort = await backendApi.fetch(`/jobs/my?tool_filter=image&limit=40`);
      if (!antwort.ok) return;
      const { jobs } = (await antwort.json()) as { jobs: Eintrag[] };
      const passend = jobs
        .filter((j) => j.has_download && (j.tool === "image_generate" || j.tool === "image_edit"))
        .slice(0, ANZAHL);
      const liste = await Promise.all(passend.map(async (j) => {
        let bild = geladen.current.get(j.job_uuid);
        if (!bild) {
          const { blob, filename } = await downloadJobAsBlob(j.job_uuid);
          bild = { jobUuid: j.job_uuid, url: URL.createObjectURL(blob), blob, filename };
          geladen.current.set(j.job_uuid, bild);
        }
        return { ...bild, ...ausMeta(j.meta), name: j.original_filename };
      }));
      setBilder(liste);
    } catch {
      // Without a history the tool still works, the strip simply stays as it was.
    }
  }, []);

  useEffect(() => {
    void laden();
    const neu = () => { void laden(); };
    window.addEventListener("kis-jobs-changed", neu);
    const karte = geladen.current;
    return () => {
      window.removeEventListener("kis-jobs-changed", neu);
      karte.forEach((b) => URL.revokeObjectURL(b.url));
    };
  }, [laden]);

  const auswahl = bilder.find((b) => b.jobUuid === gewaehlt) ?? null;

  return (
    <section className="mt-10 border-t border-border-soft pt-6">
      <h2 className="text-sm font-semibold text-foreground mb-1">{t("title")}</h2>
      <p className="text-xs text-muted mb-3">{bilder.length ? t("hint") : t("empty")}</p>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {bilder.map((b) => (
          <button
            key={b.jobUuid}
            type="button"
            onClick={() => setGewaehlt(b.jobUuid === gewaehlt ? null : b.jobUuid)}
            aria-label={t("open", { name: b.name })}
            aria-pressed={b.jobUuid === gewaehlt}
            className={`shrink-0 rounded-md border-2 p-0.5 transition-colors ${
              b.jobUuid === gewaehlt ? "border-kb" : "border-border-soft hover:border-kb"
            }`}
          >
            <img src={b.url} alt="" className="h-20 w-20 rounded object-cover" />
          </button>
        ))}
      </div>
      {auswahl && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 max-w-xs truncate text-xs text-muted">{auswahl.name}</span>
          <button type="button" className={KNOPF} onClick={() => speichern(auswahl.blob, auswahl.filename)}>
            {tResult("download", { format: "PNG" })}
          </button>
          <button type="button" className={KNOPF} onClick={() => onBearbeiten(auswahl)}>{tResult("toEdit")}</button>
          <button type="button" className={KNOPF} onClick={() => onBeschreiben(auswahl)}>{tResult("toAnalyze")}</button>
        </div>
      )}
      {auswahl?.beschreibung && (
        <div className="max-w-2xl">
          <BeschreibungText beschreibung={auswahl.beschreibung} modellPrompt={auswahl.modellPrompt}
            dateiname={auswahl.filename} />
        </div>
      )}
    </section>
  );
}
