"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import Checkbox from "@/components/ui/Checkbox";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import Auswahl from "../_components/Auswahl";
import { useZumErgebnis } from "../_components/useZumErgebnis";
import ErgebnisKarte from "../_components/ErgebnisKarte";
import { useBildAuftraege, type BildErgebnis } from "../_components/useBildAuftraege";
import { FORMATE, GROESSEN, QUALITAETEN, STILE, pixelLabel, type Format, type Groesse } from "../_utils";

interface Props {
  onUebergabe: (ziel: "edit" | "analyze", bild: BildErgebnis) => void;
}

const FELD = "w-full rounded-md border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none";

export default function GenerateTab({ onUebergabe }: Props) {
  const t = useTranslations("tools.image.generate");
  const tOpt = useTranslations("tools.image.options");
  const tImage = useTranslations("tools.image");
  const tCommon = useTranslations("common");
  const { providers, providerId, setProviderId } = useFeatureProviders("/image/providers/generate");
  const [prompt, setPrompt] = useState("");
  const [ausformuliert, setAusformuliert] = useState("");
  const [formuliert, setFormuliert] = useState(false);
  const [stil, setStil] = useState<(typeof STILE)[number]>("keiner");
  const [format, setFormat] = useState<Format>("16:9");
  const [groesse, setGroesse] = useState<Groesse>("mittel");
  const [qualitaet, setQualitaet] = useState<(typeof QUALITAETEN)[number]>("standard");
  const [varianten, setVarianten] = useState<"1" | "2" | "4">("1");
  const [ohneSchrift, setOhneSchrift] = useState(true);
  const auftraege = useBildAuftraege(t("spinner"), t("longRunning"), tCommon("unknownError"));
  const beschaeftigt = auftraege.laeuft || formuliert;

  const ausformulieren = useCallback(async () => {
    if (!prompt.trim()) return;
    setFormuliert(true);
    auftraege.setFehler("");
    try {
      const formular = new FormData();
      formular.append("prompt", prompt);
      const antwort = await backendApi.fetch("/image/enhance-prompt", { method: "POST", body: formular });
      const daten = await antwort.json().catch(() => ({}));
      if (!antwort.ok) throw new Error(parseDetail(daten.detail, tCommon("unknownError")));
      setAusformuliert(daten.prompt ?? "");
    } catch (err) {
      auftraege.setFehler(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setFormuliert(false);
    }
  }, [prompt, auftraege, tCommon]);

  const erzeugen = useCallback(() => {
    if (!prompt.trim()) return;
    const formular = new FormData();
    formular.append("prompt", prompt);
    formular.append("prompt_modell", ausformuliert);
    formular.append("stil", stil);
    formular.append("format", format);
    formular.append("groesse", groesse);
    formular.append("qualitaet", qualitaet);
    formular.append("varianten", varianten);
    formular.append("ohne_schrift", String(ohneSchrift));
    if (providerId != null) formular.append("provider_id", String(providerId));
    void auftraege.starte("/image/generate", formular);
  }, [prompt, ausformuliert, stil, format, groesse, qualitaet, varianten, ohneSchrift, providerId, auftraege]);

  const anzahl = Number(varianten);

  const ergebnisBereich = useZumErgebnis(auftraege.ergebnisse.length);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,380px)_1fr]">
      <section className="min-w-0">
        <textarea
          value={prompt}
          onChange={(e) => { setPrompt(e.target.value); setAusformuliert(""); }}
          rows={4}
          placeholder={t("promptPlaceholder")}
          className={`${FELD} mb-2`}
        />
        <button
          type="button"
          onClick={ausformulieren}
          disabled={!prompt.trim() || beschaeftigt}
          className="mb-3 px-3 py-1.5 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {formuliert ? t("enhancing") : t("enhance")}
        </button>
        {ausformuliert && (
          <div className="mb-4">
            <label htmlFor="bild-ausformuliert" className="block text-sm font-medium text-foreground-soft mb-1">
              {t("enhancedLabel")}
            </label>
            <textarea
              id="bild-ausformuliert"
              value={ausformuliert}
              onChange={(e) => setAusformuliert(e.target.value)}
              rows={5}
              className={FELD}
            />
            <p className="mt-1 text-xs text-muted">{t("enhancedHint")}</p>
          </div>
        )}

        <Auswahl label={tOpt("style")} wert={stil} onChange={setStil} disabled={beschaeftigt}
          optionen={STILE.map((s) => ({ key: s, label: tOpt(`styles.${s}`) }))} />
        <Auswahl label={tOpt("format")} wert={format} onChange={setFormat} disabled={beschaeftigt}
          optionen={FORMATE.map((f) => ({ key: f, label: tOpt(`formats.${f}`) }))} />
        <Auswahl label={tOpt("size")} wert={groesse} onChange={setGroesse} disabled={beschaeftigt}
          hinweis={pixelLabel(format, groesse)}
          optionen={GROESSEN.map((g) => ({ key: g, label: tOpt(`sizes.${g}`) }))} />
        <Auswahl label={tOpt("quality")} wert={qualitaet} onChange={setQualitaet} disabled={beschaeftigt}
          hinweis={tOpt("qualityHint")}
          optionen={QUALITAETEN.map((q) => ({ key: q, label: tOpt(`qualities.${q}`) }))} />
        <Auswahl label={tOpt("variants")} wert={varianten} onChange={setVarianten} disabled={beschaeftigt}
          optionen={(["1", "2", "4"] as const).map((n) => ({ key: n, label: n }))} />
        <div className="mb-4">
          <Checkbox checked={ohneSchrift} onChange={setOhneSchrift} label={tOpt("noText")} disabled={beschaeftigt} />
          <p className="mt-1 text-xs text-muted">{tOpt("noTextHint")}</p>
        </div>

        <ProviderSelect
          id="image-gen-provider"
          label={tImage("providerLabel")}
          providers={providers}
          value={providerId}
          onChange={setProviderId}
          disabled={beschaeftigt}
        />

        <button
          onClick={erzeugen}
          disabled={!prompt.trim() || beschaeftigt}
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
        <div className={`grid gap-4 ${auftraege.ergebnisse.length > 1 ? "sm:grid-cols-2" : ""}`}>
          {auftraege.ergebnisse.map((bild, i) => (
            <ErgebnisKarte
              key={bild.jobUuid}
              bild={bild}
              alt={t("resultAlt", { n: i + 1 })}
              onBearbeiten={(b) => onUebergabe("edit", b)}
              onBeschreiben={(b) => onUebergabe("analyze", b)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
