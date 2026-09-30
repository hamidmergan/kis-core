"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi, parseDetail } from "@/lib/api";
import Checkbox from "@/components/ui/Checkbox";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { AnbieterReihe, Band, Chips, Reihe } from "../_components/Einstellungen";
import { FORMATE, GROESSEN, QUALITAETEN, STILE, pixelLabel, type Format, type Groesse } from "../_utils";

interface Props {
  laeuft: boolean;
  offen: boolean;
  onToggle: () => void;
  onFehler: (text: string) => void;
  onStart: (formular: FormData) => void;
}

const FELD = "w-full rounded-md border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-soft hover:border-kb focus:outline-none focus:border-kb transition-colors";
const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

/** The create form: prompt, the settings band, the button, the picture itself appears on the right. */
export default function GenerateTab({ laeuft, offen, onToggle, onFehler, onStart }: Props) {
  const t = useTranslations("tools.image.generate");
  const tOpt = useTranslations("tools.image.options");
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
  const beschaeftigt = laeuft || formuliert;

  const ausformulieren = useCallback(async () => {
    if (!prompt.trim()) return;
    setFormuliert(true);
    onFehler("");
    try {
      const formular = new FormData();
      formular.append("prompt", prompt);
      const antwort = await backendApi.fetch("/image/enhance-prompt", { method: "POST", body: formular });
      const daten = await antwort.json().catch(() => ({}));
      if (!antwort.ok) throw new Error(parseDetail(daten.detail, tCommon("unknownError")));
      setAusformuliert(daten.prompt ?? "");
    } catch (err) {
      onFehler(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setFormuliert(false);
    }
  }, [prompt, onFehler, tCommon]);

  const erzeugen = () => {
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
    onStart(formular);
  };

  const anzahl = Number(varianten);
  const zusammenfassung = [tOpt(`styles.${stil}`), tOpt(`formats.${format}`), tOpt(`sizes.${groesse}`),
    tOpt(`qualities.${qualitaet}`), tOpt("imageCount", { n: anzahl })].join(", ");

  return (
    <>
      <label htmlFor="bild-prompt" className="block text-sm font-medium text-foreground-soft mb-1.5">{t("promptLabel")}</label>
      <textarea
        id="bild-prompt"
        value={prompt}
        onChange={(e) => { setPrompt(e.target.value); setAusformuliert(""); }}
        rows={4}
        placeholder={t("promptPlaceholder")}
        className={`${FELD} mb-2`}
      />
      <button type="button" onClick={ausformulieren} disabled={!prompt.trim() || beschaeftigt} className={KNOPF}>
        {formuliert ? t("enhancing") : t("enhance")}
      </button>
      {ausformuliert && (
        <div className="mt-3">
          <label htmlFor="bild-ausformuliert" className="block text-sm font-medium text-foreground-soft mb-1">
            {t("enhancedLabel")}
          </label>
          <textarea id="bild-ausformuliert" value={ausformuliert} onChange={(e) => setAusformuliert(e.target.value)}
            rows={5} className={FELD} />
          <p className="mt-1 text-xs text-muted">{t("enhancedHint")}</p>
        </div>
      )}

      <Band offen={offen} onToggle={onToggle} zusammenfassung={zusammenfassung}>
        <Reihe label={tOpt("style")}>
          <Chips label={tOpt("style")} wert={stil} onChange={setStil} disabled={beschaeftigt}
            optionen={STILE.map((s) => ({ key: s, label: tOpt(`styles.${s}`) }))} />
        </Reihe>
        <Reihe label={tOpt("format")}>
          <Chips label={tOpt("format")} wert={format} onChange={setFormat} disabled={beschaeftigt}
            optionen={FORMATE.map((f) => ({ key: f, label: tOpt(`formats.${f}`) }))} />
        </Reihe>
        <Reihe label={tOpt("size")} hinweis={pixelLabel(format, groesse)}>
          <Chips label={tOpt("size")} wert={groesse} onChange={setGroesse} disabled={beschaeftigt}
            optionen={GROESSEN.map((g) => ({ key: g, label: tOpt(`sizes.${g}`) }))} />
        </Reihe>
        <Reihe label={tOpt("quality")} hinweis={tOpt("qualityHint")}>
          <Chips label={tOpt("quality")} wert={qualitaet} onChange={setQualitaet} disabled={beschaeftigt}
            optionen={QUALITAETEN.map((q) => ({ key: q, label: tOpt(`qualities.${q}`) }))} />
        </Reihe>
        <Reihe label={tOpt("variants")}>
          <Chips label={tOpt("variants")} wert={varianten} onChange={setVarianten} disabled={beschaeftigt}
            optionen={(["1", "2", "4"] as const).map((n) => ({ key: n, label: n }))} />
        </Reihe>
        <Reihe label={tOpt("lettering")} hinweis={tOpt("noTextHint")}>
          <div className="pt-1.5">
            <Checkbox checked={ohneSchrift} onChange={setOhneSchrift} label={tOpt("noText")} disabled={beschaeftigt} />
          </div>
        </Reihe>
        <AnbieterReihe providers={providers} value={providerId} onChange={setProviderId} disabled={beschaeftigt} />
      </Band>

      <button
        type="button"
        onClick={erzeugen}
        disabled={!prompt.trim() || beschaeftigt}
        className="mt-4 w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {laeuft ? tCommon("processing") : anzahl > 1 ? t("submitMany", { n: anzahl }) : t("submit")}
      </button>
    </>
  );
}
