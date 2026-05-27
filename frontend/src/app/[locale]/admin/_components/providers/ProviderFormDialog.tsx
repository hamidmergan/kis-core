"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Eye, EyeSlash, X } from "@phosphor-icons/react";
import type { Provider, ProviderMeta, Voice } from "./_types";
import { VoicesEditor } from "./VoicesEditor";

type Props = {
  meta: ProviderMeta;
  mode: "create" | "edit";
  initial?: Provider;
  onClose: () => void;
  onSubmit: (data: {
    name: string;
    protocol: string;
    base_url: string;
    api_key: string | null;
    voices: Voice[];
  }) => Promise<void>;
};

const DEFAULT_BASE_URL: Record<string, string> = {
  openai_compat: "",
  deepl: "https://api.deepl.com",
  docling: "https://chat-ai.academiccloud.de/v1/documents/convert",
};

export default function ProviderFormDialog({
  meta,
  mode,
  initial,
  onClose,
  onSubmit,
}: Props) {
  const t = useTranslations("admin.providers");

  const [name, setName] = useState(initial?.name ?? "");
  const [protocol, setProtocol] = useState(initial?.protocol ?? meta.protocols[0]?.id ?? "openai_compat");
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? "");
  const [apiKey, setApiKey] = useState("");
  const [voices, setVoices] = useState<Voice[]>(initial?.voices ?? []);
  const [showKey, setShowKey] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = mode === "edit";

  // Show voices editor when provider has/will have tts capability
  const showVoicesEditor = useMemo(() => {
    if (isEdit) return initial?.capabilities.includes("tts") ?? false;
    // In create mode: only openai_compat can have tts
    return protocol === "openai_compat";
  }, [isEdit, initial, protocol]);

  const protocolMeta = useMemo(
    () => meta.protocols.find((p) => p.id === protocol),
    [meta.protocols, protocol],
  );

  const deeplKeyHint = useMemo(() => {
    if (protocol !== "deepl" || !apiKey.trim()) return null;
    const isFreeKey = apiKey.trim().endsWith(":fx");
    const canonical = baseUrl.trim().replace(/\/+$/, "");
    const onFreeHost = canonical === "https://api-free.deepl.com";
    const onProHost = canonical === "https://api.deepl.com";
    if (isFreeKey && onProHost) return t("dialog.deeplFreeOnProUrl");
    if (!isFreeKey && onFreeHost) return t("dialog.deeplProOnFreeUrl");
    if (isFreeKey) return t("dialog.deeplFreeDetected");
    return t("dialog.deeplProDetected");
  }, [protocol, apiKey, baseUrl, t]);

  // When the protocol is changed in create-mode, pre-fill the base URL with
  // the protocol's typical default. The admin can edit it after the change.
  useEffect(() => {
    if (isEdit) return;
    if (baseUrl) return;
    const def = DEFAULT_BASE_URL[protocol];
    if (def) setBaseUrl(def);
  }, [protocol, isEdit, baseUrl]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmedName = name.trim();
    const trimmedUrl = baseUrl.trim();
    if (!trimmedName || !trimmedUrl) {
      setError(t("validation.required"));
      return;
    }
    setSubmitting(true);
    try {
      const keyValue = apiKey === "" ? (isEdit ? null : null) : apiKey;
      await onSubmit({
        name: trimmedName,
        protocol,
        base_url: trimmedUrl,
        api_key: keyValue,
        voices,
      });
      onClose();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-background border border-border rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {isEdit ? t("dialog.titleEdit") : t("dialog.titleCreate")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-md flex items-center justify-center text-muted hover:bg-surface hover:text-kb"
            aria-label={t("dialog.close")}
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3 max-h-[80vh] overflow-y-auto pr-1" autoComplete="off">
          {/* Hidden honeypot inputs trick Chromium-based password managers
              (Google Password Manager, 1Password, LastPass) into autofilling
              into these throwaway fields instead of the real Base-URL / API-Key
              below. autoComplete="off" alone is ignored by Chrome on text+
              password siblings. */}
          <input
            type="text"
            name="username"
            autoComplete="username"
            tabIndex={-1}
            aria-hidden="true"
            style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
          />
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            tabIndex={-1}
            aria-hidden="true"
            style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
          />

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted">{t("dialog.fieldName")}</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("dialog.namePlaceholder")}
              autoComplete="off"
              data-1p-ignore
              data-lpignore="true"
              data-form-type="other"
              className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
            />
            <p className="text-xs text-muted-soft">{t("dialog.nameHint")}</p>
          </div>

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted">{t("dialog.fieldProtocol")}</label>
            <select
              value={protocol}
              onChange={(e) => setProtocol(e.target.value)}
              disabled={isEdit}
              className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {meta.protocols.map((p) => (
                <option key={p.id} value={p.id}>
                  {t(`protocolName.${p.id}`)}
                </option>
              ))}
            </select>
            {protocolMeta && protocolMeta.fixed_capabilities.length > 0 && (
              <p className="text-xs text-muted-soft">
                {t("dialog.fixedCapabilitiesHint", {
                  caps: protocolMeta.fixed_capabilities
                    .map((c) => t(`capabilityName.${c}`))
                    .join(", "),
                })}
              </p>
            )}
            {protocolMeta && protocolMeta.fixed_capabilities.length === 0 && (
              <p className="text-xs text-muted-soft">{t("dialog.probeHint")}</p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted">{t("dialog.fieldBaseUrl")}</label>
            <input
              type="url"
              required
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://..."
              spellCheck={false}
              autoComplete="off"
              data-1p-ignore
              data-lpignore="true"
              data-form-type="other"
              className="w-full text-sm border border-border rounded-md px-3 py-2 font-mono focus:outline-none focus:ring-2 focus:ring-kb"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs uppercase tracking-wide text-muted">{t("dialog.fieldApiKey")}</label>
            <div className="relative">
              {/* Use type="text" + CSS masking instead of type="password".
                  Chromium-based browsers (Chrome / Edge) heuristically offer
                  "Save password?" for ANY type="password" field on submit —
                  even with autoComplete="new-password" + data-1p-ignore.
                  WebKit-text-security visually masks the field without
                  triggering the credential-save flow. Firefox doesn't
                  support the CSS prop but its save-prompt heuristic is
                  less aggressive. */}
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={isEdit && initial?.api_key_set ? `••••••${initial.api_key_last_chars ?? ""}` : "sk-..."}
                spellCheck={false}
                autoComplete="off"
                data-1p-ignore
                data-lpignore="true"
                data-form-type="other"
                style={{ WebkitTextSecurity: showKey ? "none" : "disc" } as React.CSSProperties}
                className="w-full text-sm border border-border rounded-md px-3 py-2 pr-10 font-mono focus:outline-none focus:ring-2 focus:ring-kb"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-md flex items-center justify-center text-muted hover:text-kb"
                aria-label={showKey ? t("dialog.hideKey") : t("dialog.showKey")}
              >
                {showKey ? <EyeSlash size={14} weight="bold" /> : <Eye size={14} weight="bold" />}
              </button>
            </div>
            <p className="text-xs text-muted-soft">
              {isEdit ? t("dialog.apiKeyEditHint") : t("dialog.apiKeyHint")}
            </p>
            {deeplKeyHint && (
              <p className="text-xs text-muted">{deeplKeyHint}</p>
            )}
          </div>

          {showVoicesEditor && (
            <div className="space-y-1 pt-1 border-t border-border">
              <VoicesEditor
                voices={voices}
                onChange={setVoices}
                baseUrl={baseUrl}
                apiKey={apiKey || null}
              />
            </div>
          )}

          {error && <p className="text-sm text-error">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="btn-cancel px-4 py-2 text-sm rounded-md"
            >
              {t("dialog.cancel")}
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm bg-kb text-white rounded-md disabled:opacity-60"
            >
              {submitting ? t("dialog.saving") : t("dialog.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
