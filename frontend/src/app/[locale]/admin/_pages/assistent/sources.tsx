"use client";

/**
 * Quellen des KI-Assistenten: was hochgeladen werden darf, wie es eingelesen
 * wird und wie viel davon in eine Anfrage geht. Alles hier betrifft nur den
 * Assistenten, nicht die globalen Tools.
 *
 * Vorher lagen diese fünf Karten verstreut in einer Liste von siebzehn unter
 * "System", zwischen Wartungsmodus und Maskottchen.
 *
 * Die beiden Kontext-Budgets standen zuletzt unter einem eigenen Reiter
 * "Antworten". Der Name log: keine der beiden Zahlen beschreibt die Antwort,
 * beide zählen Quelltext, was ihre eigenen Hinweistexte auch so sagen. Sie
 * stehen deshalb hier, hinter dem Weg der Quelle vom Upload bis ins
 * Modell. Dass eines davon "Tools Kontext-Budget" heisst, klingt nach den
 * globalen Tools auf der Startseite, steuert aber die Lern-Tools im Modul. Der
 * Schlüssel im Backend bleibt wie er ist, nur der Ort stimmt jetzt.
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { useSetting } from "../../_settings/SettingsProvider";
import { NumberSetting, SelectSetting, ToggleSetting } from "../../_settings/fields";
import ReindexCard from "../../_settings/ReindexCard";

/** Grobe Schätzung, etwa 3,5 Zeichen je Token bei gemischtem Text. Nur zur
 *  Orientierung, deshalb auf Tausender gerundet. */
const approxTokens = (chars: number) => Math.round(chars / 3.5 / 1000);

export default function SourcesPage() {
  const labels = useWorkspaceLabel();
  const tLimits = useTranslations("admin.workspaceLimitsCard");
  const tPages = useTranslations("admin.sourceMaxPagesCard");
  const tOcr = useTranslations("admin.ocrCard");
  const tChat = useTranslations("admin.contextBudgetCard");
  const tSpecific = useTranslations("admin.specificBudgetCard");
  const tTools = useTranslations("admin.toolContextBudgetCard");
  const tToolLang = useTranslations("admin.learningToolsLanguageCard");
  const tLang = useTranslations("langLabels");

  const maxSources = useSetting<number>("aia_workspace_max_sources", 50);
  const maxPages = useSetting<number>("aia_source_max_pages", 200);
  const ocr = useSetting<boolean>("ocr_enabled", true);
  const chat = useSetting<number>("aia_context_max_chars", 250000);
  const specific = useSetting<number>("aia_specific_max_chars", 60000);
  const tools = useSetting<number>("aia_tool_context_max_chars", 250000);
  const toolLang = useSetting<string>("aia_learning_tools_language", "de");

  // WELCHE Sprachen es gibt, sagt das Backend (i18n.TRANSCRIPT_LANGUAGES). Wie sie
  // HEISSEN, steht in unseren eigenen langLabels, wie bei jeder anderen Sprachauswahl
  // im Haus: der Name aus dem Backend folgt Accept-Language und nicht der Sprache,
  // auf die der Admin seine Oberflaeche gestellt hat.
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
      <NumberSetting
        field={maxSources}
        title={tLimits("title", { label: labels.singular })}
        hint={tLimits("hint", { label: labels.singular })}
        unit={tLimits("unit")}
        min={1}
        max={1000}
        outOfRange={tLimits("outOfRange")}
      />
      <NumberSetting
        field={maxPages}
        title={tPages("title")}
        hint={tPages("hint")}
        unit={tPages("unit")}
        min={1}
        max={2000}
        outOfRange={tPages("outOfRange")}
      />
      <ToggleSetting
        field={ocr}
        title={tOcr("title")}
        activeText={tOcr("active")}
        disabledText={tOcr("disabled")}
        hint={tOcr("hint")}
        label={tOcr("toggleAria")}
      />
      <NumberSetting
        field={chat}
        title={tChat("title")}
        hint={tChat("hint")}
        unit={tChat("unit")}
        min={1000}
        max={800000}
        outOfRange={tChat("outOfRange")}
        suffix={(v) => (
          <span className="text-xs text-muted-soft whitespace-nowrap">
            {tChat("approxTokens", { n: approxTokens(v) })}
          </span>
        )}
      />
      <NumberSetting
        field={specific}
        title={tSpecific("title")}
        hint={tSpecific("hint")}
        unit={tSpecific("unit")}
        min={1000}
        max={800000}
        outOfRange={tSpecific("outOfRange")}
        suffix={(v) => (
          <span className="text-xs text-muted-soft whitespace-nowrap">
            {tSpecific("approxTokens", { n: approxTokens(v) })}
          </span>
        )}
      />
      <NumberSetting
        field={tools}
        title={tTools("title")}
        hint={tTools("hint")}
        unit={tTools("unit")}
        min={1000}
        max={1000000}
        outOfRange={tTools("outOfRange")}
        suffix={(v) => (
          <span className="text-xs text-muted-soft whitespace-nowrap">
            {tTools("approxTokens", { n: approxTokens(v) })}
          </span>
        )}
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
    </div>
  );
}
