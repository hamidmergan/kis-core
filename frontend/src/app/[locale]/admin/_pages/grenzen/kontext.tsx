"use client";

/** How much of the material reaches the model, grouped by who the limit applies to. */

import { useTranslations } from "next-intl";
import { useSetting } from "../../_settings/SettingsProvider";
import { NumberSetting } from "../../_settings/fields";
import Block from "./_block";

/** A rough estimate for orientation, rounded to thousands. */
const approxTokens = (chars: number) => Math.round(chars / 3.5 / 1000);

export default function GrenzenKontextPage() {
  const t = useTranslations("admin.grenzen");
  const tChat = useTranslations("admin.contextBudgetCard");
  const tSpecific = useTranslations("admin.specificBudgetCard");
  const tTools = useTranslations("admin.toolContextBudgetCard");

  const chat = useSetting<number>("aia_context_max_chars", 250000);
  const specific = useSetting<number>("aia_specific_max_chars", 60000);
  const tools = useSetting<number>("aia_tool_context_max_chars", 500000);

  const tokenHint = (label: (key: string, values: Record<string, number>) => string) =>
    (v: number) => (
      <span className="text-xs text-muted-soft whitespace-nowrap">
        {label("approxTokens", { n: approxTokens(v) })}
      </span>
    );

  return (
    <div className="space-y-8">
      <Block title={t("assistent")}>
        <NumberSetting
          field={chat}
          title={tChat("title")}
          hint={tChat("hint")}
          unit={tChat("unit")}
          min={1000}
          max={800000}
          outOfRange={tChat("outOfRange")}
          suffix={tokenHint(tChat)}
        />
        <NumberSetting
          field={specific}
          title={tSpecific("title")}
          hint={tSpecific("hint")}
          unit={tSpecific("unit")}
          min={1000}
          max={800000}
          outOfRange={tSpecific("outOfRange")}
          suffix={tokenHint(tSpecific)}
        />
      </Block>

      <Block title={t("gemeinsam")}>
        {/* The overview tools use it whole, the exercise tools only up to what their count needs. */}
        <NumberSetting
          field={tools}
          title={tTools("title")}
          hint={tTools("hint")}
          unit={tTools("unit")}
          min={1000}
          max={1000000}
          outOfRange={tTools("outOfRange")}
          suffix={tokenHint(tTools)}
        />
      </Block>
    </div>
  );
}
