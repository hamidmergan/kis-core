"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import WorkspaceLabelCard from "./WorkspaceLabelCard";
import WorkspaceExportImportCard from "./WorkspaceExportImportCard";
import DeeplKeyCard from "./DeeplKeyCard";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { notifyMascotGlobalChanged } from "@/hooks/useHildePref";

export type SettingsSection = "system" | "speech" | "images" | "embedding" | "llm";

function ProviderToggle({
  label,
  enabled,
  configured,
  available,
  envHint,
  saving,
  settingKey,
  onToggle,
  modelKey,
  modelValue,
  onModelChange,
}: {
  label: string;
  enabled: boolean;
  configured: boolean;
  available?: boolean;
  envHint?: string;
  saving: boolean;
  settingKey: string;
  onToggle: (key: string, val: boolean) => void;
  modelKey?: string;
  modelValue?: string;
  onModelChange?: (key: string, value: string) => void;
}) {
  const t = useTranslations("admin.settings");
  const usable = configured && available !== false;
  const visuallyOn = enabled && usable;
  const statusText = !configured
    ? t("providerNotConfigured")
    : !enabled
      ? t("providerDisabled")
      : available === false
        ? t("providerUnavailable")
        : t("providerActive");
  const [draft, setDraft] = React.useState(modelValue ?? "");
  React.useEffect(() => { setDraft(modelValue ?? ""); }, [modelValue]);
  const commit = () => {
    if (!modelKey || !onModelChange) return;
    const trimmed = draft.trim();
    if (!trimmed || trimmed === (modelValue ?? "")) {
      setDraft(modelValue ?? "");
      return;
    }
    onModelChange(modelKey, trimmed);
  };
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <p className="text-sm text-foreground-soft">{label}</p>
        <p className="text-xs text-muted mt-0.5">{statusText}</p>
        {!configured && envHint && (
          <p className="mt-1 text-xs text-muted-soft">
            {t.rich("envNotSet", {
              envHint,
              code: (chunks) => <code>{chunks}</code>,
            })}
          </p>
        )}
        {modelKey && onModelChange && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-muted shrink-0">{t("modelLabel")}</span>
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
              disabled={saving || !configured}
              spellCheck={false}
              className="font-mono text-xs px-3 py-1.5 border-2 border-border rounded-md w-full max-w-md transition-colors hover:border-kb focus:outline-none focus:border-kb disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-border"
            />
          </div>
        )}
      </div>
      <button
        onClick={() => onToggle(settingKey, !enabled)}
        disabled={saving || !usable}
        title={!configured && envHint ? t("envNotSetTitle", { envHint }) : undefined}
        className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
          visuallyOn ? "bg-kb" : "bg-border"
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <span
          className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
            visuallyOn ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

function ProviderSection({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <p className="text-sm font-medium text-foreground mb-1">{title}</p>
      {hint && <p className="text-xs text-muted-soft mb-4">{hint}</p>}
      {!hint && <div className="mb-3" />}
      <div className="space-y-4">
        {React.Children.toArray(children).flatMap((child, i, arr) =>
          i < arr.length - 1 ? [child, <div key={`sep-${i}`} className="border-t border-border-soft" />] : [child],
        )}
      </div>
    </div>
  );
}

function ProvidersPane({ section }: { section: Exclude<SettingsSection, "system"> }) {
  const t = useTranslations("admin.settings");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [s, setS] = useState<Record<string, any> | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setS(d));
  }, []);

  const patch = async (body: Record<string, unknown>) => {
    setSaving(true);
    try {
      await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } finally {
      setSaving(false);
    }
  };

  const EMBEDDING_KEYS = ["primary_embedding_enabled", "fallback_embedding_enabled", "local_embedding_enabled"];
  const LLM_KEYS = ["primary_llm_enabled", "fallback_llm_enabled", "local_llm_enabled"];
  const WHISPER_KEYS = ["primary_whisper_enabled", "fallback_whisper_enabled"];
  const IMAGE_GEN_KEYS = ["primary_image_gen_enabled", "fallback_image_gen_enabled"];
  const IMAGE_EDIT_KEYS = ["primary_image_edit_enabled", "fallback_image_edit_enabled"];
  const IMAGE_ANALYZE_KEYS = ["primary_image_analyze_enabled", "fallback_image_analyze_enabled"];
  const OCR_KEYS = ["primary_ocr_enabled", "fallback_ocr_enabled"];
  const RADIO_GROUPS: Record<string, string[]> = {
    embedding: EMBEDDING_KEYS,
    llm: LLM_KEYS,
    whisper: WHISPER_KEYS,
    image_gen: IMAGE_GEN_KEYS,
    image_edit: IMAGE_EDIT_KEYS,
    image_analyze: IMAGE_ANALYZE_KEYS,
    ocr: OCR_KEYS,
  };

  const toggle = async (key: string, val: boolean) => {
    const group = Object.values(RADIO_GROUPS).find((keys) => keys.includes(key));
    if (group && val) {
      const mutex: Record<string, boolean> = { [key]: true };
      for (const other of group) if (other !== key) mutex[other] = false;
      setS((prev) => (prev ? { ...prev, ...mutex } : prev));
    } else {
      setS((prev) => (prev ? { ...prev, [key]: val } : prev));
    }
    await patch({ [key]: val });
    if (EMBEDDING_KEYS.includes(key)) {
      window.dispatchEvent(new CustomEvent("embedding-provider-changed"));
    }
  };

  const setModel = async (key: string, value: string) => {
    setS((prev) => (prev ? { ...prev, models: { ...(prev.models ?? {}), [key]: value } } : prev));
    await patch({ models: { [key]: value } } as Record<string, unknown>);
    if (key.includes("embedding")) {
      window.dispatchEvent(new CustomEvent("embedding-provider-changed"));
    }
  };

  if (!s) return <Spinner className="flex justify-center py-12" />;

  const models: Record<string, string> = (s.models as Record<string, string>) ?? {};

  const P = (props: Omit<Parameters<typeof ProviderToggle>[0], "saving" | "onToggle" | "onModelChange" | "modelValue"> & { modelKey?: string }) => (
    <ProviderToggle
      {...props}
      saving={saving}
      onToggle={toggle}
      modelValue={props.modelKey ? models[props.modelKey] : undefined}
      onModelChange={props.modelKey ? setModel : undefined}
    />
  );

  return (
    <div className="space-y-4">
      {section === "speech" && (
        <>
          <ProviderSection title={t("speechTitle")}>
            <P label={t("providerElevenlabs")} settingKey="elevenlabs_enabled" enabled={s.elevenlabs_enabled ?? false} configured={s.elevenlabs_configured ?? false} envHint="ELEVENLABS_API_KEY" />
            <P label={t("providerKokoro")} settingKey="kokoro_enabled" enabled={s.kokoro_enabled ?? false} configured={s.kokoro_configured ?? false} available={s.kokoro_available} envHint="KOKORO_BASE_URL" />
            <P label={t("providerMylabXtts")} settingKey="mylab_enabled" enabled={s.mylab_enabled ?? false} configured={s.mylab_configured ?? false} available={s.mylab_available} envHint="MYLAB_TTS_BASE_URL" modelKey="mylab_tts_model" />
          </ProviderSection>

          <ProviderSection title={t("transcriptionTitle")} hint={t("transcriptionHint")}>
            <P label={t("providerKisskiWhisper")} settingKey="primary_whisper_enabled" enabled={s.primary_whisper_enabled ?? true} configured={s.primary_whisper_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" />
            <P label={t("providerMylabWhisper3")} settingKey="fallback_whisper_enabled" enabled={s.fallback_whisper_enabled ?? false} configured={s.fallback_whisper_configured ?? false} available={s.fallback_whisper_available} envHint="SECONDARY_PROVIDER_BASE_URL" />
          </ProviderSection>

          <ProviderSection title={t("translationTitle")} hint={t("translationHint")}>
            {(() => {
              const llmProv: string = s.translation_llm_provider ?? "";
              const mech: string = s.transcript_translation_provider ?? "llm";
              const active: "deepl" | "primary" | "fallback" | "local" | "" =
                mech === "deepl" ? "deepl"
                : llmProv === "primary" || llmProv === "fallback" || llmProv === "local" ? llmProv
                : "";
              const setProvider = async (target: "deepl" | "primary" | "fallback" | "local") => {
                const updates: Record<string, string> = target === "deepl"
                  ? { transcript_translation_provider: "deepl", translation_llm_provider: "" }
                  : { transcript_translation_provider: "llm", translation_llm_provider: target };
                setS((prev) => (prev ? { ...prev, ...updates } : prev));
                await patch(updates);
              };
              const T = ({ label, target, configured, modelKey, envHint }: {
                label: string;
                target: "deepl" | "primary" | "fallback" | "local";
                configured: boolean;
                modelKey?: string;
                envHint: string;
              }) => (
                <ProviderToggle
                  label={label}
                  enabled={active === target}
                  configured={configured}
                  envHint={envHint}
                  saving={saving}
                  settingKey={`translation:${target}`}
                  onToggle={(_k, val) => { if (val) setProvider(target); }}
                  modelKey={modelKey}
                  modelValue={modelKey ? models[modelKey] : undefined}
                  onModelChange={modelKey ? setModel : undefined}
                />
              );
              return (
                <>
                  <T label={t("providerDeepl")} target="deepl" configured={s.deepl_configured ?? false} envHint="DEEPL_API_KEY" />
                  <T label={t("providerKisski")} target="primary" configured={s.primary_llm_configured ?? false} modelKey="translation_primary_model" envHint="PRIMARY_PROVIDER_API_KEY" />
                  <T label={t("providerMylab")} target="fallback" configured={s.fallback_llm_configured ?? false} modelKey="translation_fallback_model" envHint="SECONDARY_PROVIDER_BASE_URL" />
                  <T label={t("providerOllama")} target="local" configured={s.local_llm_configured ?? false} modelKey="translation_local_model" envHint="LOCAL_PROVIDER_BASE_URL" />
                </>
              );
            })()}
          </ProviderSection>

          <DeeplKeyCard
            overrideSet={s.deepl_override_set ?? false}
            overrideLastChars={s.deepl_override_last_chars ?? null}
            envLastChars={s.deepl_env_last_chars ?? null}
            onChanged={() => {
              fetch("/api/admin/settings", { credentials: "include" })
                .then((r) => r.json())
                .then((d) => setS(d));
            }}
          />
        </>
      )}

      {section === "images" && (
        <>
          <ProviderSection title={t("imageGenTitle")} hint={t("imageGenHint")}>
            <P label={t("providerKisskiFlux")} settingKey="primary_image_gen_enabled" enabled={s.primary_image_gen_enabled ?? true} configured={s.primary_image_gen_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" />
            <P label={t("providerMylab")} settingKey="fallback_image_gen_enabled" enabled={s.fallback_image_gen_enabled ?? false} configured={s.fallback_image_gen_configured ?? false} available={s.fallback_image_gen_available} envHint="SECONDARY_PROVIDER_BASE_URL" modelKey="fallback_image_gen_model" />
          </ProviderSection>

          <ProviderSection title={t("imageAnalyzeTitle")} hint={t("imageAnalyzeHint")}>
            <P label={t("providerKisskiQwen")} settingKey="primary_image_analyze_enabled" enabled={s.primary_image_analyze_enabled ?? true} configured={s.primary_image_analyze_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" modelKey="primary_image_analyze_model" />
            <P label={t("providerMylab")} settingKey="fallback_image_analyze_enabled" enabled={s.fallback_image_analyze_enabled ?? false} configured={s.fallback_image_analyze_configured ?? false} available={s.fallback_image_analyze_available} envHint="SECONDARY_PROVIDER_BASE_URL" modelKey="fallback_image_analyze_model" />
          </ProviderSection>

          <ProviderSection title={t("imageEditTitle")} hint={t("imageEditHint")}>
            <P label={t("providerKisskiFlux")} settingKey="primary_image_edit_enabled" enabled={s.primary_image_edit_enabled ?? true} configured={s.primary_image_edit_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" />
            <P label={t("providerMylab")} settingKey="fallback_image_edit_enabled" enabled={s.fallback_image_edit_enabled ?? false} configured={s.fallback_image_edit_configured ?? false} available={s.fallback_image_edit_available} envHint="SECONDARY_PROVIDER_BASE_URL" modelKey="fallback_image_edit_model" />
          </ProviderSection>

          <ProviderSection title={t("ocrTitle")} hint={t("ocrHint")}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-foreground-soft">{t("ocrMasterLabel")}</p>
                <p className="text-xs text-muted mt-0.5">
                  {(s.ocr_enabled ?? true) ? t("ocrMasterOn") : t("ocrMasterOff")}
                </p>
                <p className="mt-2 text-xs text-warn-strong bg-warn-bg border border-warn-border rounded-md px-3 py-2">
                  {t("ocrMasterWarning")}
                </p>
              </div>
              <button
                onClick={() => toggle("ocr_enabled", !(s.ocr_enabled ?? true))}
                disabled={saving}
                className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
                  (s.ocr_enabled ?? true) ? "bg-kb" : "bg-border"
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <span
                  className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                    (s.ocr_enabled ?? true) ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
            <P label={t("providerKisski")} settingKey="primary_ocr_enabled" enabled={s.primary_ocr_enabled ?? true} configured={s.primary_ocr_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" modelKey="primary_ocr_model" />
            <P label={t("providerMylab")} settingKey="fallback_ocr_enabled" enabled={s.fallback_ocr_enabled ?? false} configured={s.fallback_ocr_configured ?? false} available={s.fallback_ocr_available} envHint="SECONDARY_PROVIDER_BASE_URL" modelKey="fallback_ocr_model" />
          </ProviderSection>
        </>
      )}

      {section === "embedding" && (
        <>
          <ProviderSection title={t("embeddingTitle")} hint={t("embeddingHint")}>
            <P label={t("providerKisski")} settingKey="primary_embedding_enabled" enabled={s.primary_embedding_enabled ?? true} configured={s.primary_embedding_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" modelKey="primary_embedding_model" />
            <P label={t("providerMylab")} settingKey="fallback_embedding_enabled" enabled={s.fallback_embedding_enabled ?? false} configured={s.fallback_embedding_configured ?? false} available={s.fallback_embedding_available} envHint="SECONDARY_PROVIDER_BASE_URL" modelKey="fallback_embedding_model" />
            <P label={t("providerOllama")} settingKey="local_embedding_enabled" enabled={s.local_embedding_enabled ?? false} configured={s.local_embedding_configured ?? false} envHint="LOCAL_PROVIDER_BASE_URL" modelKey="local_embedding_model" />
          </ProviderSection>

          <ReindexCard />
        </>
      )}

      {section === "llm" && (
        <>
          <ProviderSection title={t("llmTitle")} hint={t("llmHint")}>
            <P label={t("providerKisski")} settingKey="primary_llm_enabled" enabled={s.primary_llm_enabled ?? true} configured={s.primary_llm_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" modelKey="primary_llm_model" />
            <P label={t("providerMylab")} settingKey="fallback_llm_enabled" enabled={s.fallback_llm_enabled ?? false} configured={s.fallback_llm_configured ?? false} available={s.fallback_llm_available} envHint="SECONDARY_PROVIDER_BASE_URL" modelKey="fallback_llm_model" />
            <P label={t("providerOllama")} settingKey="local_llm_enabled" enabled={s.local_llm_enabled ?? false} configured={s.local_llm_configured ?? false} envHint="LOCAL_PROVIDER_BASE_URL" modelKey="local_llm_model" />
          </ProviderSection>
        </>
      )}
    </div>
  );
}

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

function BackfillDocSummaryCard() {
  const t = useTranslations("admin.backfillDocSummaryCard");
  const [pending, setPending] = useState<number | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/backfill-doc-summaries", { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        setPending(d.pending);
        setTotal(d.total);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const start = async () => {
    setWorking(true);
    setMessage("");
    try {
      const res = await fetch("/api/admin/backfill-doc-summaries", { method: "POST", credentials: "include" });
      if (!res.ok) throw new Error(t("failed"));
      setMessage(t("started"));
      setTimeout(() => void load(), 5000);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5 space-y-4">
      <div>
        <p className="text-sm font-medium text-foreground">{t("title")}</p>
        <p className="text-xs text-muted mt-1">{t("description")}</p>
      </div>
      {pending !== null && total !== null && (
        <p className="text-xs text-foreground-soft">
          {t("pendingCount", { pending, total })}
        </p>
      )}
      <div className="flex items-center gap-3">
        <button
          onClick={start}
          disabled={working || pending === 0}
          className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
        >
          {working ? "…" : t("start")}
        </button>
        {message && <p className="text-xs text-muted">{message}</p>}
      </div>
    </div>
  );
}

function BackfillPageSummaryCard() {
  const t = useTranslations("admin.backfillPageSummaryCard");
  const [pending, setPending] = useState<number | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/backfill-page-summaries", { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        setPending(d.pending);
        setTotal(d.total);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const start = async () => {
    setWorking(true);
    setMessage("");
    try {
      const res = await fetch("/api/admin/backfill-page-summaries", { method: "POST", credentials: "include" });
      if (!res.ok) throw new Error(t("failed"));
      setMessage(t("started"));
      setTimeout(() => void load(), 5000);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5 space-y-4">
      <div>
        <p className="text-sm font-medium text-foreground">{t("title")}</p>
        <p className="text-xs text-muted mt-1">{t("description")}</p>
      </div>
      {pending !== null && total !== null && (
        <p className="text-xs text-foreground-soft">
          {t("pendingCount", { pending, total })}
        </p>
      )}
      <div className="flex items-center gap-3">
        <button
          onClick={start}
          disabled={working || pending === 0}
          className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
        >
          {working ? "…" : t("start")}
        </button>
        {message && <p className="text-xs text-muted">{message}</p>}
      </div>
    </div>
  );
}

function SystemPane() {
  return (
    <div className="space-y-4">
      <MaintenanceCard />
      <WhitelistCard />
      <BackfillPageSummaryCard />
      <BackfillDocSummaryCard />
      <WorkspaceLabelCard />
      <MascotCard />
      <WorkspaceExportImportCard />
    </div>
  );
}

export default function SettingsTab({ section }: { section: SettingsSection }) {
  if (section === "system") return <SystemPane />;
  return <ProvidersPane section={section} />;
}
