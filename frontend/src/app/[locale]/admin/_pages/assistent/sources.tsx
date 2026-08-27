"use client";

/** The path of a source from upload into the model, with both context budgets. */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { useSetting } from "../../_settings/SettingsProvider";
import { NumberSetting, SelectSetting, ToggleSetting } from "../../_settings/fields";
import ReindexCard from "../../_settings/ReindexCard";
import PoolClearCard from "../../_settings/PoolClearCard";

/** A rough estimate for orientation, rounded to thousands. */
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
      {/* Direkt darunter, weil beides ein Vorgang ist und nicht eine
          Einstellung: der eine baut neu auf, der andere raeumt weg. */}
      <PoolClearCard />
    </div>
  );
}
