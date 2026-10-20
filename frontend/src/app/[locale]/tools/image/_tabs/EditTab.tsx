"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import JobCancelButton from "@/components/jobs/JobCancelButton";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { AnbieterReihe, Band, Chips, Reihe } from "../_components/Einstellungen";
import type { BildErgebnis } from "../_components/useBildAuftraege";
import { FORMATE, GROESSEN, QUALITAETEN, SCHNELLAKTIONEN, pixelLabel, type Format, type Groesse } from "../_utils";

interface Props {
  bild: BildErgebnis | null;
  laeuft: boolean;
  offen: boolean;
  onToggle: () => void;
  onStart: (formular: FormData) => void;
  onCancel: () => void;
}

const FELD = "w-full rounded-md border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-soft hover:border-kb focus:outline-none focus:border-kb transition-colors";
const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-50";

/** The edit form, it always works on the large picture on the right, one result each time. */
export default function EditTab({ bild, laeuft, offen, onToggle, onStart, onCancel }: Props) {
  const t = useTranslations("tools.image.edit");
  const tOpt = useTranslations("tools.image.options");
  const tCommon = useTranslations("common");
  const { providers, providerId, setProviderId, loading: providersLoading } = useFeatureProviders("/image/providers/edit");
  const [prompt, setPrompt] = useState("");
  const [format, setFormat] = useState<Format | "vorlage">("vorlage");
  const [groesse, setGroesse] = useState<Groesse>("mittel");
  const [qualitaet, setQualitaet] = useState<(typeof QUALITAETEN)[number]>("standard");

  const bearbeiten = () => {
    if (!bild || !prompt.trim()) return;
    const formular = new FormData();
    formular.append("image", new File([bild.blob], bild.filename, { type: bild.blob.type || "image/png" }));
    formular.append("prompt", prompt);
    formular.append("format", format);
    formular.append("groesse", groesse);
    formular.append("qualitaet", qualitaet);
    if (providerId != null) formular.append("provider_id", String(providerId));
    onStart(formular);
  };

  const zusammenfassung = [tOpt(`formats.${format}`), tOpt(`sizes.${groesse}`), tOpt(`qualities.${qualitaet}`)].join(", ");

  return (
    <>
      <label htmlFor="bild-aenderung" className="block text-sm font-medium text-foreground-soft mb-1.5">{t("promptLabel")}</label>
      <textarea
        id="bild-aenderung"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={3}
        placeholder={t("promptPlaceholder")}
        className={`${FELD} mb-2`}
      />
      <div className="flex flex-wrap gap-1.5">
        {SCHNELLAKTIONEN.map((s) => (
          <button key={s} type="button" disabled={laeuft} onClick={() => setPrompt(t(`quickPrompts.${s}`))} className={KNOPF}>
            {t(`quickActions.${s}`)}
          </button>
        ))}
      </div>

      <Band offen={offen} onToggle={onToggle} zusammenfassung={zusammenfassung}>
        <Reihe label={tOpt("format")}>
          <Chips label={tOpt("format")} wert={format} onChange={setFormat} disabled={laeuft}
            optionen={(["vorlage", ...FORMATE] as const).map((f) => ({ key: f, label: tOpt(`formats.${f}`) }))} />
        </Reihe>
        <Reihe label={tOpt("size")} hinweis={format === "vorlage" ? undefined : pixelLabel(format, groesse)}>
          <Chips label={tOpt("size")} wert={groesse} onChange={setGroesse} disabled={laeuft}
            optionen={GROESSEN.map((g) => ({ key: g, label: tOpt(`sizes.${g}`) }))} />
        </Reihe>
        <Reihe label={tOpt("quality")} hinweis={tOpt("qualityHint")}>
          <Chips label={tOpt("quality")} wert={qualitaet} onChange={setQualitaet} disabled={laeuft}
            optionen={QUALITAETEN.map((q) => ({ key: q, label: tOpt(`qualities.${q}`) }))} />
        </Reihe>
        <AnbieterReihe providers={providers} value={providerId} onChange={setProviderId} disabled={laeuft} loading={providersLoading} />
      </Band>

      <button
        type="button"
        onClick={bearbeiten}
        disabled={!bild || !prompt.trim() || laeuft}
        className="mt-4 w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {laeuft ? tCommon("processing") : t("submit")}
      </button>
      {laeuft && <div className="mt-2 flex"><JobCancelButton onClick={onCancel} /></div>}
    </>
  );
}
