"use client";

/** How material is processed, how much of it may come is set under Grenzen. */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useSetting } from "../../_settings/SettingsProvider";
import { SelectSetting, ToggleSetting } from "../../_settings/fields";
import ReindexCard from "../../_settings/ReindexCard";
import PoolClearCard from "../../_settings/PoolClearCard";

export default function SourcesPage() {
  const tOcr = useTranslations("admin.ocrCard");
  const tToolLang = useTranslations("admin.learningToolsLanguageCard");
  const tLang = useTranslations("langLabels");

  const ocr = useSetting<boolean>("ocr_enabled", true);
  const toolLang = useSetting<string>("aia_learning_tools_language", "de");

  // The languages come from the backend, the names from our own labels.
  const [codes, setCodes] = useState<{ id: string; deepl: string }[]>([]);
  useEffect(() => {
    let abgebrochen = false;
    fetch("/api/ai-assistant/transcript-languages", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (abgebrochen || !data?.languages) return;
        setCodes(data.languages.map((l: { id: string; deepl: string }) => ({ id: l.id, deepl: l.deepl })));
      })
      .catch(() => { /* die Karte bleibt dann ohne Auswahl */ });
    return () => { abgebrochen = true; };
  }, []);

  const langOptions = useMemo(
    () => codes.map((c) => ({ value: c.id, label: tLang(c.deepl) })),
    [codes, tLang],
  );

  return (
    <div className="space-y-4">
      <ToggleSetting
        field={ocr}
        title={tOcr("title")}
        activeText={tOcr("active")}
        disabledText={tOcr("disabled")}
        hint={tOcr("hint")}
        label={tOcr("toggleAria")}
      />
      <SelectSetting
        field={toolLang}
        title={tToolLang("title")}
        hint={tToolLang("hint")}
        options={langOptions}
        label={tToolLang("title")}
      />
      {/* Ganz unten, weil das als einziges hier ein Knopf ist und nicht eine
          Einstellung. Man liest die Regeln von oben nach unten und handelt am
          Ende, nicht mittendrin. */}
      <ReindexCard />
      {/* Direkt darunter, weil beides ein Vorgang ist und nicht eine
          Einstellung: der eine baut neu auf, der andere raeumt weg. */}
      <PoolClearCard />
    </div>
  );
}
