"use client";

import React, { useCallback, useEffect, useState } from "react";
import Spinner from "@/components/ui/Spinner";

function ProviderToggle({
  label,
  enabled,
  configured,
  available,
  envHint,
  saving,
  settingKey,
  onToggle,
}: {
  label: string;
  enabled: boolean;
  configured: boolean;
  available?: boolean;
  envHint?: string;
  saving: boolean;
  settingKey: string;
  onToggle: (key: string, val: boolean) => void;
}) {
  const statusText = !configured
    ? "Nicht konfiguriert."
    : !enabled
      ? "Deaktiviert — wird nicht angezeigt."
      : available === false
        ? "Aktiviert — Server nicht erreichbar."
        : "Aktiv — als Anbieter wählbar.";
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm text-gray-700">{label}</p>
        <p className="text-xs text-gray-500 mt-0.5">{statusText}</p>
        {!configured && envHint && (
          <p className="mt-1 text-xs text-gray-400">
            <code className="font-mono">{envHint}</code> nicht gesetzt
          </p>
        )}
      </div>
      <button
        onClick={() => onToggle(settingKey, !enabled)}
        disabled={saving || !configured}
        title={!configured && envHint ? `${envHint} ist nicht in .env gesetzt` : undefined}
        className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
          enabled ? "bg-primary" : "bg-gray-300"
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
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
    <div className="border border-gray-200 rounded-xl bg-white p-5">
      <p className="text-sm font-medium text-gray-800 mb-1">{title}</p>
      {hint && <p className="text-xs text-gray-400 mb-4">{hint}</p>}
      {!hint && <div className="mb-3" />}
      <div className="space-y-4">
        {React.Children.toArray(children).flatMap((child, i, arr) =>
          i < arr.length - 1 ? [child, <div key={`sep-${i}`} className="border-t border-gray-100" />] : [child],
        )}
      </div>
    </div>
  );
}

function GeneralSettingsSection() {
  const [whitelistEnabled, setWhitelistEnabled] = useState<boolean | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [s, setS] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        setWhitelistEnabled(d.whitelist_enabled ?? true);
        setS(d);
      });
  }, []);

  const patch = async (body: Record<string, boolean | string>) => {
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

  const EMBEDDING_KEYS = ["kisski_embedding_enabled", "mylab_embedding_enabled", "ollama_embedding_enabled"];
  const LLM_KEYS = ["kisski_llm_enabled", "mylab_llm_enabled", "ollama_llm_enabled"];
  const RADIO_GROUPS: Record<string, string[]> = {
    embedding: EMBEDDING_KEYS,
    llm: LLM_KEYS,
  };

  const toggle = async (key: string, val: boolean) => {
    const group = Object.values(RADIO_GROUPS).find((keys) => keys.includes(key));
    if (group && val) {
      const mutex: Record<string, boolean> = { [key]: true };
      for (const other of group) if (other !== key) mutex[other] = false;
      setS((prev) => ({ ...prev, ...mutex }));
    } else {
      setS((prev) => ({ ...prev, [key]: val }));
    }
    await patch({ [key]: val });
    if (EMBEDDING_KEYS.includes(key)) {
      window.dispatchEvent(new CustomEvent("embedding-provider-changed"));
    }
  };

  const P = (props: Omit<Parameters<typeof ProviderToggle>[0], "saving" | "onToggle">) => (
    <ProviderToggle {...props} saving={saving} onToggle={toggle} />
  );

  if (whitelistEnabled === null) return <Spinner className="flex justify-center py-12" />;

  return (
    <div className="space-y-4">
      <div className="border border-gray-200 rounded-xl bg-white p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-800">Whitelist-Modus</p>
            <p className="text-xs text-gray-500 mt-1">
              {whitelistEnabled
                ? "Aktiv — nur freigeschaltete E-Mail-Adressen dürfen sich einloggen."
                : "Deaktiviert — alle authentifizierten TH-Accounts haben Zugang."}
            </p>
          </div>
          <button
            onClick={() => {
              const v = !whitelistEnabled;
              setWhitelistEnabled(v);
              patch({ whitelist_enabled: v });
            }}
            disabled={saving}
            className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
              whitelistEnabled ? "bg-primary" : "bg-gray-300"
            } disabled:opacity-50`}
            aria-label="Whitelist umschalten"
          >
            <span
              className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                whitelistEnabled ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
        {!whitelistEnabled && (
          <p className="mt-3 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            Achtung: Alle TH-Mitarbeiter mit gültigem LDAP-Account können sich einloggen.
          </p>
        )}
      </div>

      <ProviderSection title="Text in Sprache">
        <P label="ElevenLabs" settingKey="elevenlabs_enabled" enabled={s.elevenlabs_enabled ?? false} configured={s.elevenlabs_configured ?? false} envHint="ELEVENLABS_API_KEY" />
        <P label="Kokoro TTS" settingKey="kokoro_enabled" enabled={s.kokoro_enabled ?? false} configured={s.kokoro_configured ?? false} available={s.kokoro_available} envHint="KOKORO_BASE_URL" />
        <P label="THL myLab (XTTS-v2)" settingKey="mylab_enabled" enabled={s.mylab_enabled ?? false} configured={s.mylab_configured ?? false} available={s.mylab_available} envHint="MYLAB_TTS_BASE_URL" />
        <P label="Thorsten (deutsch, lokal)" settingKey="thorsten_enabled" enabled={s.thorsten_enabled ?? false} configured={s.thorsten_configured ?? false} available={s.thorsten_available} envHint="THORSTEN_BASE_URL" />
      </ProviderSection>

      <ProviderSection title="Transkription (Sprache in Text)" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (Whisper)" settingKey="kisski_whisper_enabled" enabled={s.kisski_whisper_enabled ?? true} configured={s.kisski_whisper_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Whisper-3-large)" settingKey="mylab_whisper_enabled" enabled={s.mylab_whisper_enabled ?? false} configured={s.mylab_whisper_configured ?? false} available={s.mylab_whisper_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      <ProviderSection title="Embeddings (KI-Assistent)" hint="Nur ein Anbieter gleichzeitig — Wechsel erfordert Reindex (siehe Wartungsmodus oben).">
        <P label="KISSKI (e5-mistral-7b)" settingKey="kisski_embedding_enabled" enabled={s.kisski_embedding_enabled ?? true} configured={s.kisski_embedding_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (qwen3-embedding-4b)" settingKey="mylab_embedding_enabled" enabled={s.mylab_embedding_enabled ?? false} configured={s.mylab_embedding_configured ?? false} available={s.mylab_embedding_available} envHint="MYLAB_BASE_URL" />
        <P label="Ollama (lokal, nomic-embed-text)" settingKey="ollama_embedding_enabled" enabled={s.ollama_embedding_enabled ?? false} configured={s.ollama_embedding_configured ?? false} envHint="OLLAMA_BASE_URL" />
      </ProviderSection>

      <ProviderSection title="Bild-Generierung" hint="Ist THL myLab aktiv, wird myLab benutzt, sonst KISSKI.">
        <P label="KISSKI (Flux)" settingKey="kisski_image_gen_enabled" enabled={s.kisski_image_gen_enabled ?? true} configured={s.kisski_image_gen_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Flux.1-dev)" settingKey="mylab_image_gen_enabled" enabled={s.mylab_image_gen_enabled ?? false} configured={s.mylab_image_gen_configured ?? false} available={s.mylab_image_gen_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      <ProviderSection title="Bild-Analyse" hint="Nur KISSKI verfuegbar (THL myLab hat kein Vision-Modell).">
        <P label="KISSKI (qwen3-omni)" settingKey="kisski_image_analyze_enabled" enabled={s.kisski_image_analyze_enabled ?? true} configured={s.kisski_image_analyze_configured ?? false} envHint="KISSKI_API_KEY" />
      </ProviderSection>

      <ProviderSection title="Bild-Bearbeitung" hint="Ist THL myLab aktiv, wird myLab benutzt, sonst KISSKI.">
        <P label="KISSKI (Flux)" settingKey="kisski_image_edit_enabled" enabled={s.kisski_image_edit_enabled ?? true} configured={s.kisski_image_edit_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Flux.1-Kontext)" settingKey="mylab_image_edit_enabled" enabled={s.mylab_image_edit_enabled ?? false} configured={s.mylab_image_edit_configured ?? false} available={s.mylab_image_edit_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      <ProviderSection title="OCR (Texterkennung)" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (Docling)" settingKey="kisski_ocr_enabled" enabled={s.kisski_ocr_enabled ?? true} configured={s.kisski_ocr_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Nanonets OCR2 3B)" settingKey="mylab_ocr_enabled" enabled={s.mylab_ocr_enabled ?? false} configured={s.mylab_ocr_configured ?? false} available={s.mylab_ocr_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      <ProviderSection title="LLM Chat" hint="Nur ein Anbieter gleichzeitig. Wechsel wirkt sofort fuer alle LLM-Calls (Chat, Mindmap, Summary, Skript).">
        <P label="KISSKI (Mistral / Qwen)" settingKey="kisski_llm_enabled" enabled={s.kisski_llm_enabled ?? true} configured={s.kisski_llm_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (GPT OSS 120B)" settingKey="mylab_llm_enabled" enabled={s.mylab_llm_enabled ?? false} configured={s.mylab_llm_configured ?? false} available={s.mylab_llm_available} envHint="MYLAB_BASE_URL" />
        <P label="Ollama (lokal, qwen3)" settingKey="ollama_llm_enabled" enabled={s.ollama_llm_enabled ?? false} configured={s.ollama_llm_configured ?? false} envHint="OLLAMA_BASE_URL" />
      </ProviderSection>

      <ProviderSection title="Transkript-Übersetzung (EN)" hint="Automatische Übersetzung deutscher Video-/Audio-Transkripte ins Englische nach dem Indexieren. Betrifft aktuell nur den KI-Assistenten.">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-800">Anbieter</p>
            <p className="text-xs text-gray-500 mt-1">
              DeepL: schnell, aber Kontingent-limitiert. LLM: nutzt den konfigurierten Chat-Provider, keine zusätzliche Quote.
            </p>
          </div>
          <select
            value={s.transcript_translation_provider ?? "llm"}
            onChange={(e) => {
              const v = e.target.value;
              setS((prev) => ({ ...prev, transcript_translation_provider: v }));
              patch({ transcript_translation_provider: v });
            }}
            disabled={saving}
            className="shrink-0 border border-gray-300 rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
          >
            <option value="deepl">DeepL</option>
            <option value="llm">LLM</option>
          </select>
        </div>
      </ProviderSection>
    </div>
  );
}

interface ToolEntry {
  key: string;
  label: string;
  enabled: boolean;
}

function ToolsSettingsSection() {
  const [tools, setTools] = useState<ToolEntry[] | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setTools(d.tools ?? []));
  }, []);

  const toggle = async (key: string, enabled: boolean) => {
    setSaving(key);
    setTools((prev) => prev?.map((t) => (t.key === key ? { ...t, enabled } : t)) ?? null);
    try {
      await fetch(`/api/admin/tools/${key}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
    } finally {
      setSaving(null);
    }
  };

  if (!tools) return <Spinner className="flex justify-center py-12" />;

  return (
    <div className="border border-gray-200 rounded-xl bg-white p-5">
      <p className="text-sm font-medium text-gray-800 mb-1">Tools ein-/ausschalten</p>
      <p className="text-xs text-gray-500 mb-4">Deaktivierte Tools werden auf der Startseite ausgeblendet.</p>
      <div className="space-y-3">
        {tools.map((tool) => (
          <div key={tool.key} className="flex items-center justify-between">
            <span className="text-sm text-gray-700">{tool.label}</span>
            <button
              onClick={() => toggle(tool.key, !tool.enabled)}
              disabled={saving === tool.key}
              className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
                tool.enabled ? "bg-primary" : "bg-gray-300"
              } disabled:opacity-50`}
              aria-label={`${tool.label} ${tool.enabled ? "deaktivieren" : "aktivieren"}`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                  tool.enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        ))}
      </div>
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

function MaintenanceSection() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [progress, setProgress] = useState<ReindexProgress | null>(null);
  const [staleModules, setStaleModules] = useState<{ uuid: string; title: string; owner: string | null }[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/maintenance", { credentials: "include" });
      const d = await res.json();
      setEnabled(!!d.enabled);
      setProgress(d.reindex ?? null);
      setStaleModules(Array.isArray(d.stale_modules) ? d.stale_modules : []);
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

  const startReindex = async () => {
    if (!enabled) {
      setError("Bitte zuerst Wartungsmodus aktivieren.");
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

  if (enabled === null) return null;

  const pct = progress && progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;

  return (
    <div className="border border-gray-200 rounded-xl bg-white p-5 space-y-4">
      {staleModules.length > 0 && !progress?.running && (
        <div className="bg-amber-50 border border-amber-200 rounded-md px-3 py-2 text-xs text-amber-800 space-y-2">
          <div>
            <strong>Hinweis:</strong> {staleModules.length} Workspace
            {staleModules.length === 1 ? "" : "s"} wurde{staleModules.length === 1 ? "" : "n"} mit einem anderen Embedding-Modell indexiert. Chat-Suche kann fehlschlagen, bis du unten &quot;Reindex starten&quot; ausführst.
          </div>
          <ul className="list-disc pl-5 space-y-0.5">
            {staleModules.map((m) => (
              <li key={m.uuid}>
                <span className="font-medium">{m.title}</span>
                {m.owner && <span className="text-amber-700"> — {m.owner}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-gray-800">Wartungsmodus</p>
          <p className="text-xs text-gray-500 mt-1">
            {enabled
              ? "Aktiv — alle Nicht-Admin-Anfragen erhalten eine Wartungsseite."
              : "Deaktiviert — App ist normal nutzbar."}
          </p>
        </div>
        <button
          onClick={() => toggle(!enabled)}
          disabled={working || !!progress?.running}
          className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
            enabled ? "bg-red-500" : "bg-gray-300"
          } disabled:opacity-50`}
          aria-label="Wartungsmodus umschalten"
        >
          <span
            className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>

      <div className="border-t border-gray-100 pt-4 space-y-3">
        <div>
          <p className="text-sm font-medium text-gray-800">Alle Quellen neu indexieren</p>
          <p className="text-xs text-gray-500 mt-1">
            Berechnet alle Embeddings mit dem aktuellen Anbieter neu. Chips, Notizen und Tools bleiben gültig (gleiche UUIDs). Nötig nach Wechsel des Embedding-Modells.
          </p>
        </div>
        {progress?.running ? (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-gray-600">
              <span>Läuft: {progress.current}</span>
              <span>
                {progress.done}/{progress.total} ({pct}%)
              </span>
            </div>
            <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
            {progress.failed > 0 && (
              <p className="text-xs text-red-600">{progress.failed} Fehler — siehe Backend-Logs.</p>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <button
              onClick={startReindex}
              disabled={working || !enabled}
              className="px-3 py-1.5 text-xs font-medium text-white bg-primary hover:opacity-90 rounded-md disabled:opacity-40"
            >
              {working ? "…" : "Reindex starten"}
            </button>
            {progress && !progress.running && progress.done > 0 && (
              <p className="text-xs text-gray-500">
                Letzter Lauf: {progress.done}/{progress.total} fertig
                {progress.failed > 0 ? `, ${progress.failed} Fehler` : ""}.
              </p>
            )}
            {!enabled && (
              <p className="text-xs text-gray-400">Wartungsmodus aktivieren, bevor du startest.</p>
            )}
          </div>
        )}
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}

export default function SettingsTab() {
  return (
    <div className="space-y-6">
      <MaintenanceSection />
      <GeneralSettingsSection />
      <ToolsSettingsSection />
    </div>
  );
}
