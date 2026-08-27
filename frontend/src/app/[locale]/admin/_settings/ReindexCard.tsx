"use client";

/** Re-ingest all sources, an action that requires maintenance mode. */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";

interface ReindexProgress {
  total: number;
  done: number;
  current: string;
  failed: number;
  running: boolean;
}

export default function ReindexCard() {
  const t = useTranslations("admin.reindexCard");
  const labels = useWorkspaceLabel();
  const [maintenanceEnabled, setMaintenanceEnabled] = useState<boolean | null>(null);
  const [progress, setProgress] = useState<ReindexProgress | null>(null);
  const [staleModules, setStaleModules] = useState<{ uuid: string; title: string; owner: string | null }[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/maintenance", { credentials: "include" });
      const d = await res.json();
      setMaintenanceEnabled(!!d.enabled);
      setProgress(d.reindex ?? null);
      setStaleModules(Array.isArray(d.stale_workspaces) ? d.stale_workspaces : []);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Poll only while the run is going, not afterwards.
  useEffect(() => {
    if (!progress?.running) return;
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [progress?.running, load]);

  // Check again right away after a provider change.
  useEffect(() => {
    const handler = () => load();
    window.addEventListener("embedding-provider-changed", handler);
    return () => window.removeEventListener("embedding-provider-changed", handler);
  }, [load]);

  const startReindex = async () => {
    if (!maintenanceEnabled) {
      setError(t("needsMaintenance"));
      return;
    }
    setWorking(true);
    setError("");
    try {
      const res = await fetch("/api/admin/reindex-all", { method: "POST", credentials: "include" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? t("couldNotStart"));
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  };

  if (maintenanceEnabled === null) return null;

  const pct = progress && progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5 space-y-4">
      {staleModules.length > 0 && !progress?.running && (
        <div className="bg-warn-bg border border-warn-border rounded-md px-3 py-2 text-xs text-warn-strong space-y-2">
          <div>
            {t.rich("staleNotice", {
              n: staleModules.length,
              label: staleModules.length === 1 ? labels.singular : labels.plural,
              strong: (chunks) => <strong>{chunks}</strong>,
            })}
          </div>
          <ul className="list-disc pl-5 space-y-0.5">
            {staleModules.map((m) => (
              <li key={m.uuid}>
                <span className="font-medium">{m.title}</span>
                {m.owner && <span className="text-warn-strong"> - {m.owner}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <p className="text-sm font-medium text-foreground">{t("title")}</p>
        <p className="text-xs text-muted mt-1">{t("description")}</p>
      </div>
      {progress?.running ? (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-foreground-soft">
            <span>{t("running", { current: progress.current })}</span>
            <span>{t("progressCount", { done: progress.done, total: progress.total, pct })}</span>
          </div>
          <div className="w-full h-2 bg-surface-dim rounded-full overflow-hidden">
            <div className="h-full bg-kb transition-all" style={{ width: `${pct}%` }} />
          </div>
          {progress.failed > 0 && (
            <p className="text-xs text-error">{t("errorsHint", { n: progress.failed })}</p>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={startReindex}
            disabled={working || !maintenanceEnabled}
            className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
          >
            {working ? "…" : t("start")}
          </button>
          {progress && !progress.running && progress.done > 0 && (
            <p className="text-xs text-muted">
              {t("lastRun", {
                done: progress.done,
                total: progress.total,
                failed: progress.failed > 0 ? t("lastRunFailed", { n: progress.failed }) : "",
              })}
            </p>
          )}
          {!maintenanceEnabled && (
            <p className="text-xs text-muted-soft">{t("activateMaintenance")}</p>
          )}
        </div>
      )}
      {error && <p className="text-xs text-error">{error}</p>}
    </div>
  );
}
