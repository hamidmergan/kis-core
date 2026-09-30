"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import Auswahl from "../_components/Auswahl";
import { useZumErgebnis } from "../_components/useZumErgebnis";
import BildWahl from "../_components/BildWahl";
import ErgebnisKarte from "../_components/ErgebnisKarte";
import VorherNachher from "../_components/VorherNachher";
import { useBildAuftraege, type BildErgebnis } from "../_components/useBildAuftraege";
import { FORMATE, GROESSEN, QUALITAETEN, SCHNELLAKTIONEN, pixelLabel, type Format, type Groesse, type Uebergabe } from "../_utils";

interface Props {
  uebergabe: Uebergabe | null;
  onUebergabe: (ziel: "edit" | "analyze", bild: BildErgebnis) => void;
}

export default function EditTab({ uebergabe, onUebergabe }: Props) {
  const t = useTranslations("tools.image.edit");
  const tOpt = useTranslations("tools.image.options");
  const tImage = useTranslations("tools.image");
  const tCommon = useTranslations("common");
  const { providers, providerId, setProviderId } = useFeatureProviders("/image/providers/edit");
  const [datei, setDatei] = useState<File | null>(null);
  const [vorlageUrl, setVorlageUrl] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [format, setFormat] = useState<Format | "vorlage">("vorlage");
  const [groesse, setGroesse] = useState<Groesse>("mittel");
  const [qualitaet, setQualitaet] = useState<(typeof QUALITAETEN)[number]>("standard");
  const [varianten, setVarianten] = useState<"1" | "2">("1");
  const auftraege = useBildAuftraege(t("spinner"), t("longRunning"), tCommon("unknownError"));
  const { zuruecksetzen } = auftraege;
  useEffect(() => { zuruecksetzen(); }, [datei, zuruecksetzen]);

  useEffect(() => {
    if (!datei) { setVorlageUrl(null); return; }
    const url = URL.createObjectURL(datei);
    setVorlageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [datei]);

  const bearbeiten = useCallback(() => {
    if (!datei || !prompt.trim()) return;
    const formular = new FormData();
    formular.append("image", datei);
    formular.append("prompt", prompt);
    formular.append("format", format);
    formular.append("groesse", groesse);
    formular.append("qualitaet", qualitaet);
    formular.append("varianten", varianten);
    if (providerId != null) formular.append("provider_id", String(providerId));
    void auftraege.starte("/image/edit", formular);
  }, [datei, prompt, format, groesse, qualitaet, varianten, providerId, auftraege]);

  const anzahl = Number(varianten);

  const ergebnisBereich = useZumErgebnis(auftraege.ergebnisse.length);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,380px)_1fr]">
      <section className="min-w-0">
        <BildWahl datei={datei} onDatei={setDatei} onFehler={auftraege.setFehler} uebergabe={uebergabe}
          disabled={auftraege.laeuft} label={t("source")} />
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder={t("promptPlaceholder")}
          className="w-full rounded-md border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none mb-2"
        />
        <div className="mb-4">
          <p className="text-xs font-medium text-muted mb-1.5">{t("quick")}</p>
          <div className="flex flex-wrap gap-1.5">
            {SCHNELLAKTIONEN.map((s) => (
              <button
                key={s}
                type="button"
                disabled={auftraege.laeuft}
                onClick={() => setPrompt(t(`quickPrompts.${s}`))}
                className="px-2.5 py-1 text-xs rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-50"
              >
                {t(`quickActions.${s}`)}
              </button>
            ))}
          </div>
        </div>

        <Auswahl label={tOpt("format")} wert={format} onChange={setFormat} disabled={auftraege.laeuft}
          optionen={(["vorlage", ...FORMATE] as const).map((f) => ({ key: f, label: tOpt(`formats.${f}`) }))} />
        <Auswahl label={tOpt("size")} wert={groesse} onChange={setGroesse} disabled={auftraege.laeuft}
          hinweis={format === "vorlage" ? undefined : pixelLabel(format, groesse)}
          optionen={GROESSEN.map((g) => ({ key: g, label: tOpt(`sizes.${g}`) }))} />
        <Auswahl label={tOpt("quality")} wert={qualitaet} onChange={setQualitaet} disabled={auftraege.laeuft}
          hinweis={tOpt("qualityHint")}
          optionen={QUALITAETEN.map((q) => ({ key: q, label: tOpt(`qualities.${q}`) }))} />
        <Auswahl label={tOpt("variants")} wert={varianten} onChange={setVarianten} disabled={auftraege.laeuft}
          optionen={(["1", "2"] as const).map((n) => ({ key: n, label: n }))} />

        <ProviderSelect
          id="image-edit-provider"
          label={tImage("providerLabel")}
          providers={providers}
          value={providerId}
          onChange={setProviderId}
          disabled={auftraege.laeuft}
        />

        <button
          onClick={bearbeiten}
          disabled={!datei || !prompt.trim() || auftraege.laeuft}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {auftraege.laeuft ? tCommon("processing") : anzahl > 1 ? t("submitMany", { n: anzahl }) : t("submit")}
        </button>
      </section>

      <section ref={ergebnisBereich} className="min-w-0 scroll-mt-4 self-start rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5" aria-live="polite">
        <h2 className="text-sm font-semibold text-foreground mb-3">{tImage("result.title")}</h2>
        {auftraege.laeuft && <Spinner label={auftraege.label} className="mb-4" />}
        {auftraege.laeuft && <BackgroundHint />}
        {auftraege.fehler && <p className="mb-4 text-sm text-error" role="alert">{auftraege.fehler}</p>}
        {auftraege.teilweise && (
          <p className="mb-4 text-sm text-foreground-soft">{tImage("result.partial", auftraege.teilweise)}</p>
        )}
        {!auftraege.laeuft && !auftraege.ergebnisse.length && !auftraege.fehler && (
          <p className="text-sm text-muted">{tImage("result.empty")}</p>
        )}
        <div className="grid gap-4">
          {auftraege.ergebnisse.map((bild, i) => (
            <ErgebnisKarte
              key={bild.jobUuid}
              bild={bild}
              alt={t("resultAlt", { n: i + 1 })}
              onBearbeiten={(b) => onUebergabe("edit", b)}
              onBeschreiben={(b) => onUebergabe("analyze", b)}
              vorschau={vorlageUrl ? (
                <VorherNachher vorher={vorlageUrl} nachher={bild.url} labelVorher={t("before")}
                  labelNachher={t("after")} labelRegler={t("compareLabel")} />
              ) : undefined}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
