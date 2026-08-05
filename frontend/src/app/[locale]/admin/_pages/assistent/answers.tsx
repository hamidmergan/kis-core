"use client";

/**
 * Wie viel Quelltext in eine Anfrage geht.
 *
 * Beide Budgets betreffen den KI-Assistenten. Dass eines davon "Tools
 * Kontext-Budget" heisst, ist der beste Beleg für die Umsortierung: es klingt
 * nach den globalen Tools auf der Startseite, steuert aber die Lern-Tools im
 * Modul. Der Schlüssel im Backend bleibt wie er ist, nur der Ort stimmt jetzt.
 */

import { useTranslations } from "next-intl";
import { useSetting } from "../../_settings/SettingsProvider";
import { NumberSetting } from "../../_settings/fields";

/** Grobe Schätzung, etwa 3,5 Zeichen je Token bei gemischtem Text. Nur zur
 *  Orientierung, deshalb auf Tausender gerundet. */
const approxTokens = (chars: number) => Math.round(chars / 3.5 / 1000);

export default function AnswersPage() {
  const tChat = useTranslations("admin.contextBudgetCard");
  const tTools = useTranslations("admin.toolContextBudgetCard");

  const chat = useSetting<number>("aia_context_max_chars", 60000);
  const tools = useSetting<number>("aia_tool_context_max_chars", 250000);

  return (
    <div className="space-y-4">
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
    </div>
  );
}
