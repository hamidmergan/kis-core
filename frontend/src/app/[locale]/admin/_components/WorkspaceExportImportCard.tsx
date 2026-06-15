"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { DownloadSimple, UploadSimple } from "@phosphor-icons/react";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";

interface WorkspaceListEntry {
  uuid: string;
  title: string;
  is_active: boolean;
  embedding_fingerprint: string | null;
  owner: string | null;
  source_count: number;
  chunk_count: number;
}

interface ImportResult {
  ok: boolean;
  workspace_uuid: string;
  sources_imported: number;
  chunks_imported: number;
  transcripts_restored?: number;
  files_missing: number;
  needs_reindex: boolean;
  bundle_embedding_model: string | null;
  extras_imported?: Record<string, unknown>;
}

type ExtraKey = "glossary" | "notes" | "schedule" | "studio";
const EXTRA_KEYS: ExtraKey[] = ["glossary", "notes", "schedule", "studio"];

export default function WorkspaceExportImportCard() {
  const t = useTranslations("admin.workspaceExportImport");
  const labels = useWorkspaceLabel();
  const [list, setList] = useState<WorkspaceListEntry[] | null>(null);
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [reindexing, setReindexing] = useState<string | null>(null);
  const [extras, setExtras] = useState<Record<ExtraKey, boolean>>({
    glossary: false, notes: false, schedule: false, studio: false,
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleExtra = (k: ExtraKey) =>
    setExtras((prev) => ({ ...prev, [k]: !prev[k] }));

  const allChecked = EXTRA_KEYS.every((k) => extras[k]);
  const anyChecked = EXTRA_KEYS.some((k) => extras[k]);
  const someButNotAll = anyChecked && !allChecked;
  const allCheckboxRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (allCheckboxRef.current) allCheckboxRef.current.indeterminate = someButNotAll;
  }, [someButNotAll]);

  const toggleAll = () => {
    const next = !allChecked;
    setExtras({
      glossary: next, notes: next, schedule: next, studio: next,
    });
  };

  const buildExportUrl = (uuid: string) => {
    const enabled = EXTRA_KEYS.filter((k) => extras[k]);
    const qs = enabled.length ? "?" + enabled.map((k) => `${k}=1`).join("&") : "";
    return `/api/admin/aia-workspaces/${uuid}/export${qs}`;
  };

  const triggerDownload = (uuid: string) => {
    // Programmatic anchor click avoids the global NextTopLoader navigation indicator
    // that fires for any <a href> click to a same-origin URL.
    const a = document.createElement("a");
    a.href = buildExportUrl(uuid);
    a.download = "";
    a.click();
  };

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/aia-workspaces", { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setList(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onPickFile = () => fileInputRef.current?.click();

  const onFileChosen = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    setImportResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/admin/aia-workspaces/import", {
        method: "POST",
        credentials: "include",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setImportResult(data as ImportResult);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setImporting(false);
    }
  };

  const triggerReindex = async (uuid: string) => {
    setReindexing(uuid);
    setError("");
    try {
      const res = await fetch(`/api/admin/aia-workspaces/${uuid}/reindex`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `HTTP ${res.status}`);
      }
      setImportResult((prev) => (prev && prev.workspace_uuid === uuid ? { ...prev, needs_reindex: false } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReindexing(null);
    }
  };

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">{t("title")}</p>
          <p className="text-xs text-muted mt-1">{t("description", { label: labels.singular })}</p>
        </div>
        <button
          onClick={onPickFile}
          disabled={importing}
          className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md inline-flex items-center gap-1.5 disabled:opacity-40"
        >
          <UploadSimple size={14} weight="bold" />
          {importing ? t("importing") : t("importButton")}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip,application/zip"
          className="hidden"
          onChange={onFileChosen}
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border-soft pt-3">
        <span className="text-xs text-muted shrink-0">{t("extrasLabel")}</span>
        <label className="flex items-center gap-1.5 text-xs font-medium text-foreground cursor-pointer select-none">
          <input
            ref={allCheckboxRef}
            type="checkbox"
            checked={allChecked}
            onChange={toggleAll}
            className="h-3.5 w-3.5 rounded border-border accent-kb"
          />
          {t("extra_all")}
        </label>
        <span className="h-3 w-px bg-border-soft" aria-hidden />
        {EXTRA_KEYS.map((k) => (
          <label key={k} className="flex items-center gap-1.5 text-xs text-foreground-soft cursor-pointer select-none">
            <input
              type="checkbox"
              checked={extras[k]}
              onChange={() => toggleExtra(k)}
              className="h-3.5 w-3.5 rounded border-border accent-kb"
            />
            {t(`extra_${k}`)}
          </label>
        ))}
      </div>

      {importResult && (
        <div className="bg-success-bg border border-success-border rounded-md px-3 py-2 text-xs text-success-strong space-y-2">
          <div>
            {t("importDone", {
              sources: importResult.sources_imported,
              chunks: importResult.chunks_imported,
            })}
            {importResult.files_missing > 0 && (
              <span className="ml-1">
                {t("filesMissing", { n: importResult.files_missing })}
              </span>
            )}
          </div>
          {importResult.needs_reindex && (
            <div className="flex items-center gap-2 pt-1">
              <span>{t("needsReindex", { model: importResult.bundle_embedding_model ?? "?" })}</span>
              <button
                onClick={() => triggerReindex(importResult.workspace_uuid)}
                disabled={reindexing === importResult.workspace_uuid}
                className="btn-primary px-2 py-1 text-xs rounded-md disabled:opacity-40"
              >
                {reindexing === importResult.workspace_uuid ? "…" : t("reindexNow")}
              </button>
            </div>
          )}
        </div>
      )}

      {error && <p className="text-xs text-error">{error}</p>}

      {list === null ? (
        <p className="text-xs text-muted">{t("loading")}</p>
      ) : list.length === 0 ? (
        <p className="text-xs text-muted">{t("empty")}</p>
      ) : (
        <div className="border border-border-soft rounded-md overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-xs text-muted uppercase">
                <th className="px-3 py-2">{labels.singular}</th>
                <th className="px-3 py-2">{t("colOwner")}</th>
                <th className="px-3 py-2 text-right">{t("colSources")}</th>
                <th className="px-3 py-2 text-right">{t("colChunks")}</th>
                <th className="px-3 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {list.map((w) => (
                <tr key={w.uuid} className="border-t border-border-soft">
                  <td className="px-3 py-1.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 ${w.is_active ? "bg-success-border" : "bg-border"}`}
                      />
                      <span className="font-medium text-foreground-soft truncate max-w-[260px]" title={w.title}>
                        {w.title}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 text-foreground-soft truncate max-w-[160px]">{w.owner ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right text-foreground-soft">{w.source_count}</td>
                  <td className="px-3 py-1.5 text-right text-foreground-soft">{w.chunk_count}</td>
                  <td className="px-3 py-1.5 text-right">
                    <button
                      type="button"
                      onClick={() => triggerDownload(w.uuid)}
                      className="inline-flex items-center justify-center w-7 h-7 rounded hover:bg-surface text-muted hover:text-kb"
                      title={t("exportButton")}
                      aria-label={t("exportButton")}
                    >
                      <DownloadSimple size={14} weight="bold" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
