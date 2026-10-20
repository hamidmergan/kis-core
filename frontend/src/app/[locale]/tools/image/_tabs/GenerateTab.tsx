"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import JobCancelButton from "@/components/jobs/JobCancelButton";
import Checkbox from "@/components/ui/Checkbox";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { AnbieterReihe, Band, Chips, Reihe } from "../_components/Einstellungen";
import type { PromptEntwurf } from "../_components/PromptFeld";
import { FORMATE, GROESSEN, QUALITAETEN, STILE, pixelLabel, type Format, type Groesse } from "../_utils";

interface Props {
  entwurf: PromptEntwurf;
  laeuft: boolean;
  offen: boolean;
  onToggle: () => void;
  onStart: (formular: FormData) => void;
  onCancel: () => void;
}

/** The create settings and the button, the prompt itself and later the picture stand on the right. */
export default function GenerateTab({ entwurf, laeuft, offen, onToggle, onStart, onCancel }: Props) {
  const t = useTranslations("tools.image.generate");
  const tOpt = useTranslations("tools.image.options");
  const tCommon = useTranslations("common");
  const { providers, providerId, setProviderId, loading: providersLoading } = useFeatureProviders("/image/providers/generate");
  const { prompt, ausformuliert } = entwurf;
  const [stil, setStil] = useState<(typeof STILE)[number]>("keiner");
  const [format, setFormat] = useState<Format>("16:9");
  const [groesse, setGroesse] = useState<Groesse>("mittel");
  const [qualitaet, setQualitaet] = useState<(typeof QUALITAETEN)[number]>("standard");
  const [varianten, setVarianten] = useState<"1" | "2" | "4">("1");
  const [ohneSchrift, setOhneSchrift] = useState(true);
  const beschaeftigt = laeuft || entwurf.formuliert;

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
      <Band className="" offen={offen} onToggle={onToggle} zusammenfassung={zusammenfassung}>
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
        <AnbieterReihe providers={providers} value={providerId} onChange={setProviderId} disabled={beschaeftigt} loading={providersLoading} />
      </Band>

      <button
        type="button"
        onClick={erzeugen}
        disabled={!prompt.trim() || beschaeftigt}
        className="mt-4 w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {laeuft ? tCommon("processing") : anzahl > 1 ? t("submitMany", { n: anzahl }) : t("submit")}
      </button>
      {laeuft && <div className="mt-2 flex"><JobCancelButton onClick={onCancel} /></div>}
    </>
  );
}
