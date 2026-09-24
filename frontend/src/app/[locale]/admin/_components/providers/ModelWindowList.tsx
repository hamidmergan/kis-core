"use client";

import { useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import HelpTooltip from "@/components/ui/HelpTooltip";
import { setModelWindow } from "./_api";
import type { ModelWindow } from "./_types";

const FELD =
  "w-24 text-xs px-1.5 py-1 border-2 border-border rounded-md font-mono text-right " +
  "hover:border-kb focus:outline-none focus:border-kb bg-background " +
  "disabled:opacity-60 disabled:cursor-not-allowed";

/** The context window of every model this provider is routed to, one field each. */
export default function ModelWindowList({
  models,
  fallbackTokens,
  onSaved,
}: {
  models: ModelWindow[];
  fallbackTokens: number;
  onSaved: () => Promise<void> | void;
}) {
  const t = useTranslations("admin.providers.windows");
  const format = useFormatter();
  if (models.length === 0) return null;
  const fallback = format.number(fallbackTokens);

  return (
    <div className="mt-3 flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5 text-2xs text-muted-soft">
        {t("title")}
        <HelpTooltip text={t("help")} />
      </div>
      {models.map((m) => (
        <WindowRow key={m.model_name} model={m} fallback={fallback} onSaved={onSaved} />
      ))}
    </div>
  );
}

function WindowRow({
  model,
  fallback,
  onSaved,
}: {
  model: ModelWindow;
  fallback: string;
  onSaved: () => Promise<void> | void;
}) {
  const t = useTranslations("admin.providers.windows");
  const format = useFormatter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (roh: string) => {
    const text = roh.replace(/[.,'\s]/g, "");
    const wert = text === "" ? null : Number(text);
    if (wert === model.window_tokens) return;
    if (wert !== null && (!Number.isInteger(wert) || wert <= 0)) {
      setError(t("notANumber"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await setModelWindow(model.provider_id, model.model_name, wert);
      await onSaved();
    } catch (err) {
      setError(detail((err as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const status = busy
    ? t("measuring")
    : model.window_tokens == null
      ? t("source.unbekannt", { fallback })
      : t(`source.${model.source}`);

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-2">
        <span className="flex-1 min-w-0 truncate text-2xs font-mono text-foreground-soft">
          {model.model_name}
        </span>
        <input
          key={`${model.model_name}-${model.window_tokens ?? ""}`}
          type="text"
          inputMode="numeric"
          defaultValue={model.window_tokens != null ? format.number(model.window_tokens) : ""}
          placeholder={t("empty")}
          disabled={busy}
          aria-label={t("fieldLabel", { model: model.model_name })}
          onBlur={(e) => save(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className={FELD}
        />
        <span className="w-60 shrink-0 text-2xs text-muted-soft">{status}</span>
      </div>
      {error && <p className="text-2xs text-error">{error}</p>}
    </div>
  );
}

// The backend answers errors as JSON with a detail field.
function detail(nachricht: string): string {
  try {
    return JSON.parse(nachricht).detail ?? nachricht;
  } catch {
    return nachricht;
  }
}
