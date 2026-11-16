"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { AnbieterReihe, Band, Chips, Reihe } from "../_components/Einstellungen";
import type { BildErgebnis } from "../_components/useBildAuftraege";
import type { Frage } from "../_components/useBildFragen";
import { AUFGABEN, FELD, START_KNOPF } from "../_utils";

interface Props {
  bild: BildErgebnis | null;
  laeuft: boolean;
  offen: boolean;
  onToggle: () => void;
  onStart: (frage: Frage) => void;
}

/** The describe form, it asks about the large picture on the right, the answer appears below that picture. */
export default function AnalyzeTab({ bild, laeuft, offen, onToggle, onStart }: Props) {
  const t = useTranslations("tools.image.analyze");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { providers, providerId, setProviderId, loading: providersLoading } = useFeatureProviders("/image/providers/analyze");
  const [aufgabe, setAufgabe] = useState<Frage["aufgabe"]>("beschreiben");
  const [sprache, setSprache] = useState<Frage["sprache"]>(locale === "en" ? "en" : "de");
  const [frage, setFrage] = useState("");

  const starten = () => {
    if (!bild || (aufgabe === "frage" && !frage.trim())) return;
    onStart({ aufgabe, text: frage, titel: aufgabe === "frage" ? frage : t(`tasks.${aufgabe}`), sprache, providerId });
  };

  return (
    <>
      <p className="text-sm font-medium text-foreground-soft mb-2">{t("task")}</p>
      <Chips label={t("task")} wert={aufgabe} onChange={setAufgabe} disabled={laeuft}
        optionen={AUFGABEN.map((a) => ({ key: a, label: t(`tasks.${a}`) }))} />
      {aufgabe === "frage" && (
        <textarea value={frage} onChange={(e) => setFrage(e.target.value)} rows={3}
          placeholder={t("questionPlaceholder")} className={`${FELD} mt-3`} />
      )}

      <Band offen={offen} onToggle={onToggle} zusammenfassung={t("summary", { sprache: t(`languages.${sprache}`) })}>
        <Reihe label={t("language")}>
          <Chips label={t("language")} wert={sprache} onChange={setSprache} disabled={laeuft}
            optionen={(["de", "en"] as const).map((s) => ({ key: s, label: t(`languages.${s}`) }))} />
        </Reihe>
        <AnbieterReihe providers={providers} value={providerId} onChange={setProviderId} disabled={laeuft} loading={providersLoading} />
      </Band>

      <button
        type="button"
        onClick={starten}
        disabled={!bild || laeuft || (aufgabe === "frage" && !frage.trim())}
        className={START_KNOPF}
      >
        {laeuft ? tCommon("processing") : t(`submits.${aufgabe}`)}
      </button>
    </>
  );
}
