"use client";

/** Clearing pools is an action and takes effect platform wide. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import Checkbox from "@/components/ui/Checkbox";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";

import { chosenCount, POOL_TOOLS, type PoolCounts } from "./poolSelection";

export default function PoolClearCard() {
  const t = useTranslations("admin.poolClearCard");
  const tTools = useTranslations("workspace.detail.langTools");
  const [counts, setCounts] = useState<PoolCounts | null>(null);
  const [tools, setTools] = useState<string[]>([]);
  const [schedule, setSchedule] = useState(false);
  const [asking, setAsking] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/pools", { credentials: "include" });
      if (!res.ok) return;
      const d = await res.json();
      setCounts({ tools: d.tools ?? {}, schedule: d.schedule ?? 0 });
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleTool = (tool: string, an: boolean) =>
    setTools((alt) => (an ? [...alt, tool] : alt.filter((x) => x !== tool)));

  const clear = async () => {
    setError("");
    setNote("");
    try {
      const res = await fetch("/api/admin/pools/clear", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tools, schedule }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? t("failed"));
      }
      const d = await res.json();
      setNote(t("done", { items: d.items_deleted, extractions: d.extractions_deleted }));
      setTools([]);
      setSchedule(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAsking(false);
    }
  };

  if (!counts) return null;

  const gewaehlt = chosenCount(counts, tools, schedule);
  const nichts = tools.length === 0 && !schedule;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5 space-y-4">
      <div>
        <p className="text-sm font-medium text-foreground">{t("title")}</p>
        <p className="text-xs text-muted mt-1">{t("description")}</p>
      </div>
      {/* The number sits right after the name; pushed to the right edge it was too far away to tell which row it belongs to. */}
      <div className="grid gap-2 sm:grid-cols-2">
        {POOL_TOOLS.map((tool) => (
          <div key={tool} className="flex items-center gap-1.5">
            <Checkbox
              checked={tools.includes(tool)}
              onChange={(an) => toggleTool(tool, an)}
              label={tTools(tool)}
            />
            <span className="text-xs text-muted-soft whitespace-nowrap">
              ({t("items", { n: counts.tools[tool] ?? 0 })})
            </span>
          </div>
        ))}
        <div className="flex items-center gap-1.5">
          <Checkbox checked={schedule} onChange={setSchedule} label={t("schedule")} />
          <span className="text-xs text-muted-soft whitespace-nowrap">
            ({t("sources", { n: counts.schedule })})
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => setAsking(true)}
          disabled={nichts}
          className="btn-danger px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
        >
          {t("clear")}
        </button>
        {note && <p className="text-xs text-muted">{note}</p>}
      </div>
      {error && <p className="text-xs text-error">{error}</p>}
      {asking && (
        <ConfirmDialog
          count={gewaehlt}
          onCancel={() => setAsking(false)}
          onConfirm={clear}
        />
      )}
    </div>
  );
}

/** Confirmation, it lives here because it belongs to this card alone. */
function ConfirmDialog({
  count, onCancel, onConfirm,
}: {
  count: number;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  const t = useTranslations("admin.poolClearCard");
  const [laeuft, setLaeuft] = useState(false);
  const press = useRef(newBackdropPress()).current;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !laeuft) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, laeuft]);

  const bestaetigen = async () => {
    setLaeuft(true);
    try {
      await onConfirm();
    } finally {
      setLaeuft(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      {...backdropClose(press, () => { if (!laeuft) onCancel(); })}
    >
      <div
        className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-base font-semibold mb-2">{t("confirmTitle")}</h3>
        <p className="text-sm text-foreground-soft mb-1">{t("confirmBody", { n: count })}</p>
        <p className="text-sm text-foreground-soft mb-6">{t("confirmWarning")}</p>
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            disabled={laeuft}
            className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={bestaetigen}
            disabled={laeuft}
            className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50"
          >
            {t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
