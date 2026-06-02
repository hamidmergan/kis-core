"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import WorkspaceLabelCard from "./WorkspaceLabelCard";
import WorkspaceExportImportCard from "./WorkspaceExportImportCard";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { notifyMascotGlobalChanged } from "@/hooks/useHildePref";

export type SettingsSection = "system";

function WhitelistCard() {
  const t = useTranslations("admin.whitelistCard");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setEnabled(d.whitelist_enabled ?? true));
  }, []);

  const toggle = async () => {
    if (enabled === null) return;
    const next = !enabled;
    setEnabled(next);
    setSaving(true);
    try {
      await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ whitelist_enabled: next }),
      });
    } finally {
      setSaving(false);
    }
  };

  if (enabled === null) return null;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">{t("title")}</p>
          <p className="text-xs text-muted mt-1">
            {enabled ? t("active") : t("disabled")}
          </p>
        </div>
        <button
          onClick={toggle}
          disabled={saving}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
            enabled ? "bg-kb" : "bg-border"
          } disabled:opacity-50`}
          aria-label={t("toggleAria")}
        >
          <span
            className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>
      {!enabled && (
        <p className="mt-3 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {t("warningOff")}
        </p>
      )}
    </div>
  );
}

interface ReindexProgress {
  total: number;
  done: number;
  current: string;
  failed: number;
  running: boolean;
}

function MaintenanceCard() {
  const t = useTranslations("admin.maintenanceCard");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/admin/maintenance", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setEnabled(!!d.enabled))
      .catch(() => {});
  }, []);

  const toggle = async (value: boolean) => {
    setWorking(true);
    setError("");
    try {
      const res = await fetch("/api/admin/maintenance", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: value }),
      });
      if (!res.ok) throw new Error(t("toggleFailed"));
      setEnabled(value);
    } catch (e) {
      setError(String(e));
    } finally {
      setWorking(false);
    }
  };

  if (enabled === null) return null;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">{t("title")}</p>
          <p className="text-xs text-muted mt-1">
            {enabled ? t("active") : t("disabled")}
          </p>
        </div>
        <button
          onClick={() => toggle(!enabled)}
          disabled={working}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-error ${
            enabled ? "bg-error" : "bg-border"
          } disabled:opacity-50`}
          aria-label={t("toggleAria")}
        >
          <span
            className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>
      {error && <p className="mt-3 text-xs text-error">{error}</p>}
    </div>
  );
}

function ReindexCard() {
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

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!progress?.running) return;
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [progress?.running, load]);

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
        <div className="flex items-center gap-3">
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

function MascotCard() {
  const t = useTranslations("admin.mascotCard");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setEnabled(d.mascot_enabled ?? true));
  }, []);

  const toggle = async () => {
    if (enabled === null) return;
    const next = !enabled;
    setEnabled(next);
    setSaving(true);
    try {
      await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mascot_enabled: next }),
      });
      notifyMascotGlobalChanged();
    } finally {
      setSaving(false);
    }
  };

  if (enabled === null) return null;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">{t("title")}</p>
          <p className="text-xs text-muted mt-1">
            {enabled ? t("active") : t("disabled")}
          </p>
        </div>
        <button
          onClick={toggle}
          disabled={saving}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
            enabled ? "bg-kb" : "bg-border"
          } disabled:opacity-50`}
          aria-label={t("toggleAria")}
        >
          <span
            className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>
    </div>
  );
}

function WorkspaceLimitsCard() {
  const t = useTranslations("admin.workspaceLimitsCard");
  const labels = useWorkspaceLabel();
  const [value, setValue] = useState<number | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const n = typeof d.aia_workspace_max_sources === "number" ? d.aia_workspace_max_sources : 30;
        setValue(n);
        setDraft(String(n));
      });
  }, []);

  const commit = async () => {
    if (value === null) return;
    const parsed = Number.parseInt(draft, 10);
    if (!Number.isFinite(parsed) || parsed < 1 || parsed > 1000) {
      setError(t("outOfRange"));
      setDraft(String(value));
      return;
    }
    if (parsed === value) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ aia_workspace_max_sources: parsed }),
      });
      if (res.ok) {
        setValue(parsed);
      } else {
        let detail = t("saveFailed");
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
          else if (body?.detail?.message) detail = body.detail.message;
        } catch { /* ignore */ }
        setError(detail);
        setDraft(String(value));
      }
    } finally {
      setSaving(false);
    }
  };

  if (value === null) return null;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">{t("title", { label: labels.singular })}</p>
      <p className="text-xs text-muted-soft mt-1">{t("hint", { label: labels.singular })}</p>
      <div className="mt-3 flex items-center gap-3">
        <input
          type="number"
          min={1}
          max={1000}
          value={draft}
          onChange={(e) => { setDraft(e.target.value); setError(null); }}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
          disabled={saving}
          className="font-mono text-sm px-3 py-1.5 border-2 border-border rounded-md w-28 transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
        />
        <span className="text-xs text-muted">{t("unit")}</span>
      </div>
      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}

function ScheduleRetentionCard() {
  const t = useTranslations("admin.scheduleRetentionCard");
  const [value, setValue] = useState<number | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const n = typeof d.aia_schedule_retention_days === "number" ? d.aia_schedule_retention_days : -1;
        setValue(n);
        setDraft(n < 0 ? "" : String(n));
      });
  }, []);

  const commit = async () => {
    if (value === null) return;
    const trimmed = draft.trim();
    let parsed: number;
    if (trimmed === "") {
      parsed = -1;
    } else {
      const n = Number.parseInt(trimmed, 10);
      if (!Number.isFinite(n) || n < 1 || n > 3650) {
        setError(t("outOfRange"));
        setDraft(value < 0 ? "" : String(value));
        return;
      }
      parsed = n;
    }
    if (parsed === value) {
      setDraft(value < 0 ? "" : String(value));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ aia_schedule_retention_days: parsed }),
      });
      if (res.ok) {
        setValue(parsed);
        setDraft(parsed < 0 ? "" : String(parsed));
      } else {
        let detail = t("saveFailed");
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
          else if (body?.detail?.message) detail = body.detail.message;
        } catch { /* ignore */ }
        setError(detail);
        setDraft(value < 0 ? "" : String(value));
      }
    } finally {
      setSaving(false);
    }
  };

  if (value === null) return null;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">{t("title")}</p>
      <p className="text-xs text-muted-soft mt-1">{t("hint")}</p>
      <div className="mt-3 flex items-center gap-3">
        <input
          type="number"
          min={1}
          max={3650}
          value={draft}
          placeholder={t("placeholderNever")}
          onChange={(e) => { setDraft(e.target.value); setError(null); }}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
          disabled={saving}
          className="font-mono text-sm px-3 py-1.5 border-2 border-border rounded-md w-32 transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
        />
        <span className="text-xs text-muted">{t("unit")}</span>
        <span className="text-xs text-muted-soft">
          {value < 0 ? t("modeNever") : t("modeDays", { n: value })}
        </span>
      </div>
      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}

function ContextBudgetCard() {
  const t = useTranslations("admin.contextBudgetCard");
  const [value, setValue] = useState<number | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const n = typeof d.aia_context_max_chars === "number" ? d.aia_context_max_chars : 60000;
        setValue(n);
        setDraft(String(n));
      });
  }, []);

  const commit = async () => {
    if (value === null) return;
    const parsed = Number.parseInt(draft, 10);
    if (!Number.isFinite(parsed) || parsed < 1000 || parsed > 500000) {
      setError(t("outOfRange"));
      setDraft(String(value));
      return;
    }
    if (parsed === value) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ aia_context_max_chars: parsed }),
      });
      if (res.ok) {
        setValue(parsed);
      } else {
        let detail = t("saveFailed");
        try {
          const body = await res.json();
          if (typeof body?.detail === "string") detail = body.detail;
          else if (body?.detail?.message) detail = body.detail.message;
        } catch { /* ignore */ }
        setError(detail);
        setDraft(String(value));
      }
    } finally {
      setSaving(false);
    }
  };

  if (value === null) return null;

  // Rough token estimate (~3.5 chars/token, mixed DE/non-Latin) just for orientation.
  const approxTokens = Math.round((Number.parseInt(draft, 10) || value) / 3.5 / 1000);

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground">{t("title")}</p>
      <p className="text-xs text-muted-soft mt-1">{t("hint")}</p>
      <div className="mt-3 flex items-center gap-3">
        <input
          type="number"
          min={1000}
          max={500000}
          step={1000}
          value={draft}
          onChange={(e) => { setDraft(e.target.value); setError(null); }}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
          disabled={saving}
          className="font-mono text-sm px-3 py-1.5 border-2 border-border rounded-md w-36 transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50"
        />
        <span className="text-xs text-muted">{t("unit")}</span>
        <span className="text-xs text-muted-soft">{t("approxTokens", { n: approxTokens })}</span>
      </div>
      {error && (
        <p className="mt-2 text-xs text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}

function SystemPane() {
  return (
    <div className="space-y-4">
      <MaintenanceCard />
      <WhitelistCard />
      <ReindexCard />
      <WorkspaceLabelCard />
      <WorkspaceLimitsCard />
      <ScheduleRetentionCard />
      <ContextBudgetCard />
      <MascotCard />
      <WorkspaceExportImportCard />
    </div>
  );
}

export default function SettingsTab(_: { section: SettingsSection }) {
  return <SystemPane />;
}
