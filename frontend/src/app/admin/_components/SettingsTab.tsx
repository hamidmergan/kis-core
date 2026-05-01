"use client";

import React, { useCallback, useEffect, useState } from "react";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import WorkspaceLabelCard from "./WorkspaceLabelCard";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { notifyMascotGlobalChanged } from "@/hooks/useHildePref";

const TRANSLATION_MODE_OPTIONS = [
  { value: "off", label: "Aus" },
  { value: "auto", label: "Auto (bei Ingest)" },
  { value: "manual", label: "Manuell (Button)" },
] as const;

const TRANSLATION_PROVIDER_OPTIONS = [
  { value: "deepl", label: "DeepL" },
  { value: "llm", label: "LLM" },
] as const;

type TranslationMode = typeof TRANSLATION_MODE_OPTIONS[number]["value"];
type TranslationProvider = typeof TRANSLATION_PROVIDER_OPTIONS[number]["value"];

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
  const statusText = !configured
    ? "Nicht konfiguriert."
    : !enabled
      ? "Deaktiviert - wird nicht angezeigt."
      : available === false
        ? "Aktiviert - Server nicht erreichbar."
        : "Aktiv - als Anbieter wählbar.";
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
            <code className="font-mono">{envHint}</code> nicht gesetzt
          </p>
        )}
        {modelKey && onModelChange && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-muted shrink-0">Modell:</span>
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
        disabled={saving || !configured}
        title={!configured && envHint ? `${envHint} ist nicht in .env gesetzt` : undefined}
        className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
          enabled ? "bg-kb" : "bg-border"
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <span
          className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
            enabled ? "translate-x-5" : "translate-x-0"
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
    <div className="border border-border-soft rounded-xl bg-white p-5">
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
  const RADIO_GROUPS: Record<string, string[]> = {
    embedding: EMBEDDING_KEYS,
    llm: LLM_KEYS,
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
          <ProviderSection title="Text in Sprache">
            <P label="ElevenLabs" settingKey="elevenlabs_enabled" enabled={s.elevenlabs_enabled ?? false} configured={s.elevenlabs_configured ?? false} envHint="ELEVENLABS_API_KEY" />
            <P label="Kokoro TTS" settingKey="kokoro_enabled" enabled={s.kokoro_enabled ?? false} configured={s.kokoro_configured ?? false} available={s.kokoro_available} envHint="KOKORO_BASE_URL" />
            <P label="THL myLab (XTTS-v2)" settingKey="mylab_enabled" enabled={s.mylab_enabled ?? false} configured={s.mylab_configured ?? false} available={s.mylab_available} envHint="MYLAB_TTS_BASE_URL" modelKey="mylab_tts_model" />
          </ProviderSection>

          <ProviderSection title="Transkription (Sprache in Text)" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
            <P label="KISSKI (Whisper)" settingKey="primary_whisper_enabled" enabled={s.primary_whisper_enabled ?? true} configured={s.primary_whisper_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" />
            <P label="THL myLab (Whisper-3-large)" settingKey="fallback_whisper_enabled" enabled={s.fallback_whisper_enabled ?? false} configured={s.fallback_whisper_configured ?? false} available={s.fallback_whisper_available} envHint="FALLBACK_PROVIDER_BASE_URL" />
          </ProviderSection>

          <ProviderSection title="Transkript-Übersetzung (EN)" hint="Übersetzung deutscher Video-/Audio-Transkripte ins Englische. Betrifft aktuell nur den KI-Assistenten.">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-foreground">Modus</p>
                <p className="text-xs text-muted mt-1">
                  Aus: keine EN-Übersetzung. Auto: direkt beim Indexieren. Manuell: nur über den Button im Transkript-Panel (Default).
                </p>
              </div>
              <Select<TranslationMode>
                value={(s.transcript_translation_mode ?? "manual") as TranslationMode}
                onChange={(v) => {
                  setS((prev) => (prev ? { ...prev, transcript_translation_mode: v } : prev));
                  patch({ transcript_translation_mode: v });
                }}
                options={TRANSLATION_MODE_OPTIONS}
                disabled={saving}
                className="shrink-0 w-48"
              />
            </div>
            <div className="flex items-center justify-between gap-4" style={{ opacity: (s.transcript_translation_mode ?? "manual") === "off" ? 0.5 : 1 }}>
              <div>
                <p className="text-sm font-medium text-foreground">Anbieter</p>
                <p className="text-xs text-muted mt-1">
                  DeepL: schnell, aber Kontingent-limitiert. LLM: nutzt den konfigurierten Chat-Provider, keine zusätzliche Quote.
                </p>
              </div>
              <Select<TranslationProvider>
                value={(s.transcript_translation_provider ?? "llm") as TranslationProvider}
                onChange={(v) => {
                  setS((prev) => (prev ? { ...prev, transcript_translation_provider: v } : prev));
                  patch({ transcript_translation_provider: v });
                }}
                options={TRANSLATION_PROVIDER_OPTIONS}
                disabled={saving || (s.transcript_translation_mode ?? "manual") === "off"}
                className="shrink-0 w-48"
              />
            </div>
          </ProviderSection>
        </>
      )}

      {section === "images" && (
        <>
          <ProviderSection title="Bild-Generierung" hint="Ist THL myLab aktiv, wird myLab benutzt, sonst KISSKI.">
            <P label="KISSKI (Flux)" settingKey="primary_image_gen_enabled" enabled={s.primary_image_gen_enabled ?? true} configured={s.primary_image_gen_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" />
            <P label="THL myLab" settingKey="fallback_image_gen_enabled" enabled={s.fallback_image_gen_enabled ?? false} configured={s.fallback_image_gen_configured ?? false} available={s.fallback_image_gen_available} envHint="FALLBACK_PROVIDER_BASE_URL" modelKey="fallback_image_gen_model" />
          </ProviderSection>

          <ProviderSection title="Bild-Analyse" hint="Nur KISSKI verfuegbar (THL myLab hat kein Vision-Modell).">
            <P label="KISSKI (qwen3-omni)" settingKey="primary_image_analyze_enabled" enabled={s.primary_image_analyze_enabled ?? true} configured={s.primary_image_analyze_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" />
          </ProviderSection>

          <ProviderSection title="Bild-Bearbeitung" hint="Ist THL myLab aktiv, wird myLab benutzt, sonst KISSKI.">
            <P label="KISSKI (Flux)" settingKey="primary_image_edit_enabled" enabled={s.primary_image_edit_enabled ?? true} configured={s.primary_image_edit_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" />
            <P label="THL myLab" settingKey="fallback_image_edit_enabled" enabled={s.fallback_image_edit_enabled ?? false} configured={s.fallback_image_edit_configured ?? false} available={s.fallback_image_edit_available} envHint="FALLBACK_PROVIDER_BASE_URL" modelKey="fallback_image_edit_model" />
          </ProviderSection>

          <ProviderSection title="OCR (Texterkennung)" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
            <P label="KISSKI" settingKey="primary_ocr_enabled" enabled={s.primary_ocr_enabled ?? true} configured={s.primary_ocr_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" modelKey="primary_ocr_model" />
            <P label="THL myLab" settingKey="fallback_ocr_enabled" enabled={s.fallback_ocr_enabled ?? false} configured={s.fallback_ocr_configured ?? false} available={s.fallback_ocr_available} envHint="FALLBACK_PROVIDER_BASE_URL" modelKey="fallback_ocr_model" />
          </ProviderSection>
        </>
      )}

      {section === "embedding" && (
        <>
          <ProviderSection title="Embeddings (KI-Assistent)" hint="Nur ein Anbieter gleichzeitig - Wechsel erfordert Reindex (siehe unten).">
            <P label="KISSKI" settingKey="primary_embedding_enabled" enabled={s.primary_embedding_enabled ?? true} configured={s.primary_embedding_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" modelKey="primary_embedding_model" />
            <P label="THL myLab" settingKey="fallback_embedding_enabled" enabled={s.fallback_embedding_enabled ?? false} configured={s.fallback_embedding_configured ?? false} available={s.fallback_embedding_available} envHint="FALLBACK_PROVIDER_BASE_URL" modelKey="fallback_embedding_model" />
            <P label="Ollama (lokal)" settingKey="local_embedding_enabled" enabled={s.local_embedding_enabled ?? false} configured={s.local_embedding_configured ?? false} envHint="LOCAL_PROVIDER_BASE_URL" modelKey="local_embedding_model" />
          </ProviderSection>

          <ReindexCard />
        </>
      )}

      {section === "llm" && (
        <>
          <ProviderSection title="LLM Chat" hint="Nur ein Anbieter gleichzeitig. Wechsel wirkt sofort fuer alle LLM-Calls (Chat, Mindmap, Summary, Skript).">
            <P label="KISSKI" settingKey="primary_llm_enabled" enabled={s.primary_llm_enabled ?? true} configured={s.primary_llm_configured ?? false} envHint="PRIMARY_PROVIDER_API_KEY" modelKey="primary_llm_model" />
            <P label="THL myLab" settingKey="fallback_llm_enabled" enabled={s.fallback_llm_enabled ?? false} configured={s.fallback_llm_configured ?? false} available={s.fallback_llm_available} envHint="FALLBACK_PROVIDER_BASE_URL" modelKey="fallback_llm_model" />
            <P label="Ollama (lokal)" settingKey="local_llm_enabled" enabled={s.local_llm_enabled ?? false} configured={s.local_llm_configured ?? false} envHint="LOCAL_PROVIDER_BASE_URL" modelKey="local_llm_model" />
          </ProviderSection>

          <ProviderSection title="LLM-Übersetzung (/translate)" hint="Optionaler Provider+Modell-Override nur für Datei-Übersetzung. Keiner aktiv = nutzt das aktive LLM oben.">
            {(() => {
              const tProvider: string = s.translation_llm_provider ?? "";
              const toggleProvider = async (target: "primary" | "fallback" | "local", on: boolean) => {
                const next = on ? target : "";
                setS((prev) => (prev ? { ...prev, translation_llm_provider: next } : prev));
                await patch({ translation_llm_provider: next });
              };
              const T = ({ label, target, configured, modelKey, envHint }: {
                label: string; target: "primary" | "fallback" | "local"; configured: boolean; modelKey: string; envHint: string;
              }) => (
                <ProviderToggle
                  label={label}
                  enabled={tProvider === target}
                  configured={configured}
                  envHint={envHint}
                  saving={saving}
                  settingKey={`translation_llm_provider:${target}`}
                  onToggle={(_k, val) => toggleProvider(target, val)}
                  modelKey={modelKey}
                  modelValue={models[modelKey]}
                  onModelChange={setModel}
                />
              );
              return (
                <>
                  <T label="KISSKI" target="primary" configured={s.primary_llm_configured ?? false} modelKey="translation_primary_model" envHint="PRIMARY_PROVIDER_API_KEY" />
                  <T label="THL myLab" target="fallback" configured={s.fallback_llm_configured ?? false} modelKey="translation_fallback_model" envHint="FALLBACK_PROVIDER_BASE_URL" />
                  <T label="Ollama (lokal)" target="local" configured={s.local_llm_configured ?? false} modelKey="translation_local_model" envHint="LOCAL_PROVIDER_BASE_URL" />
                </>
              );
            })()}
          </ProviderSection>
        </>
      )}
    </div>
  );
}

function WhitelistCard() {
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
    <div className="border border-border-soft rounded-xl bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">Whitelist-Modus</p>
          <p className="text-xs text-muted mt-1">
            {enabled
              ? "Aktiv - nur freigeschaltete E-Mail-Adressen dürfen sich einloggen."
              : "Deaktiviert - alle authentifizierten TH-Accounts haben Zugang."}
          </p>
        </div>
        <button
          onClick={toggle}
          disabled={saving}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
            enabled ? "bg-kb" : "bg-border"
          } disabled:opacity-50`}
          aria-label="Whitelist umschalten"
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
          Achtung: Alle TH-Mitarbeiter mit gültigem LDAP-Account können sich einloggen.
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
      if (!res.ok) throw new Error("Toggle fehlgeschlagen");
      setEnabled(value);
    } catch (e) {
      setError(String(e));
    } finally {
      setWorking(false);
    }
  };

  if (enabled === null) return null;

  return (
    <div className="border border-border-soft rounded-xl bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">Wartungsmodus</p>
          <p className="text-xs text-muted mt-1">
            {enabled
              ? "Aktiv - alle Nicht-Admin-Anfragen erhalten eine Wartungsseite."
              : "Deaktiviert - App ist normal nutzbar."}
          </p>
        </div>
        <button
          onClick={() => toggle(!enabled)}
          disabled={working}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-error ${
            enabled ? "bg-error" : "bg-border"
          } disabled:opacity-50`}
          aria-label="Wartungsmodus umschalten"
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
      setError("Bitte zuerst Wartungsmodus aktivieren (Tab \"System\").");
      return;
    }
    setWorking(true);
    setError("");
    try {
      const res = await fetch("/api/admin/reindex-all", { method: "POST", credentials: "include" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? "Reindex konnte nicht gestartet werden");
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
    <div className="border border-border-soft rounded-xl bg-white p-5 space-y-4">
      {staleModules.length > 0 && !progress?.running && (
        <div className="bg-warn-bg border border-warn-border rounded-md px-3 py-2 text-xs text-warn-strong space-y-2">
          <div>
            <strong>Hinweis:</strong> {staleModules.length} {staleModules.length === 1 ? labels.singular : labels.plural} wurde{staleModules.length === 1 ? "" : "n"} mit einem anderen Embedding-Modell indexiert. Chat-Suche kann fehlschlagen, bis du unten &quot;Reindex starten&quot; ausführst.
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
        <p className="text-sm font-medium text-foreground">Alle Quellen neu indexieren</p>
        <p className="text-xs text-muted mt-1">
          Berechnet alle Embeddings mit dem aktuellen Anbieter neu. Chips, Notes und Tools bleiben gültig (gleiche UUIDs). Nötig nach Wechsel des Embedding-Modells.
        </p>
      </div>
      {progress?.running ? (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-foreground-soft">
            <span>Läuft: {progress.current}</span>
            <span>
              {progress.done}/{progress.total} ({pct}%)
            </span>
          </div>
          <div className="w-full h-2 bg-surface-dim rounded-full overflow-hidden">
            <div className="h-full bg-kb transition-all" style={{ width: `${pct}%` }} />
          </div>
          {progress.failed > 0 && (
            <p className="text-xs text-error">{progress.failed} Fehler - siehe Backend-Logs.</p>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <button
            onClick={startReindex}
            disabled={working || !maintenanceEnabled}
            className="btn-primary px-3 py-1.5 text-xs font-medium rounded-md disabled:opacity-40"
          >
            {working ? "…" : "Reindex starten"}
          </button>
          {progress && !progress.running && progress.done > 0 && (
            <p className="text-xs text-muted">
              Letzter Lauf: {progress.done}/{progress.total} fertig
              {progress.failed > 0 ? `, ${progress.failed} Fehler` : ""}.
            </p>
          )}
          {!maintenanceEnabled && (
            <p className="text-xs text-muted-soft">Wartungsmodus aktivieren (Tab &quot;System&quot;), bevor du startest.</p>
          )}
        </div>
      )}
      {error && <p className="text-xs text-error">{error}</p>}
    </div>
  );
}

function MascotCard() {
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
    <div className="border border-border-soft rounded-xl bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">Hilde-Maskottchen</p>
          <p className="text-xs text-muted mt-1">
            {enabled
              ? "Aktiv - die Eulen-Begleiterin wird systemweit angezeigt; jeder Nutzer kann sie für sich abschalten."
              : "Deaktiviert - Hilde wird nirgendwo angezeigt, der Nutzer-Toggle in den KI-Assistent-Einstellungen ist ausgeblendet."}
          </p>
        </div>
        <button
          onClick={toggle}
          disabled={saving}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-kb ${
            enabled ? "bg-kb" : "bg-border"
          } disabled:opacity-50`}
          aria-label="Maskottchen umschalten"
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

function SystemPane() {
  return (
    <div className="space-y-4">
      <MaintenanceCard />
      <WhitelistCard />
      <WorkspaceLabelCard />
      <MascotCard />
    </div>
  );
}

export default function SettingsTab({ section }: { section: SettingsSection }) {
  if (section === "system") return <SystemPane />;
  return <ProvidersPane section={section} />;
}
