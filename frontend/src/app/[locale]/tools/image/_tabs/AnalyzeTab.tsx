"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { AnbieterReihe, Band, Chips, Reihe } from "../_components/Einstellungen";
import type { BildErgebnis } from "../_components/useBildAuftraege";
import { AUFGABEN } from "../_utils";

type Aufgabe = (typeof AUFGABEN)[number];

export interface FrageStart {
  aufgabe: Aufgabe;
  text: string;
  titel: string;
  sprache: "de" | "en";
  providerId: number | null;
}

interface Props {
  bild: BildErgebnis | null;
  laeuft: boolean;
  offen: boolean;
  onToggle: () => void;
  onStart: (frage: FrageStart) => void;
}

const FELD = "w-full rounded-md border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-soft hover:border-kb focus:outline-none focus:border-kb transition-colors";

/** The describe form, it asks about the large picture on the right, the answer appears below that picture. */
export default function AnalyzeTab({ bild, laeuft, offen, onToggle, onStart }: Props) {
  const t = useTranslations("tools.image.analyze");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { providers, providerId, setProviderId, loading: providersLoading } = useFeatureProviders("/image/providers/analyze");
  const [aufgabe, setAufgabe] = useState<Aufgabe>("beschreiben");
  const [sprache, setSprache] = useState<"de" | "en">(locale === "en" ? "en" : "de");
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
        className="mt-4 w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {laeuft ? tCommon("processing") : t(`submits.${aufgabe}`)}
      </button>
    </>
  );
}
