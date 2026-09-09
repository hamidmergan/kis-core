"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Play, Stop } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { Voice } from "./_types";
import { discoverVoices } from "./_api";
import { useVoicePlayer } from "@/hooks/useVoicePlayer";

interface Props {
  voices: Voice[];
  onChange: (voices: Voice[]) => void;
  baseUrl: string;
  apiKey?: string | null;
  voicesPath: string;
  onVoicesPathChange: (path: string) => void;
  providerId?: number;
}

const EMPTY_VOICE: Voice = { voice_id: "", name: "", language: "", description: "" };

export function VoicesEditor({ voices, onChange, baseUrl, apiKey, voicesPath, onVoicesPathChange, providerId }: Props) {
  const t = useTranslations("admin.providers");
  const [discovering, setDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState<string | null>(null);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const { playingId, loadingId, playFromApi } = useVoicePlayer();
  const [addingRow, setAddingRow] = useState(false);
  const [newVoice, setNewVoice] = useState<Voice>(EMPTY_VOICE);

  async function handleDiscover() {
    if (!baseUrl) return;
    setDiscovering(true);
    setDiscoverError(null);
    try {
      const result = await discoverVoices(baseUrl, apiKey, voicesPath || null);
      if (!result.discoverable || result.voices.length === 0) {
        setDiscoverError(t("voices.notDiscoverable"));
        return;
      }
      const existing = new Set(voices.map((v) => v.voice_id));
      const merged = [
        ...voices,
        ...result.voices.filter((v) => !existing.has(v.voice_id)),
      ];
      onChange(merged);
    } catch {
      setDiscoverError(t("voices.discoverFailed"));
    } finally {
      setDiscovering(false);
    }
  }

  function handleRemove(idx: number) {
    onChange(voices.filter((_, i) => i !== idx));
    if (expandedIdx === idx) setExpandedIdx(null);
    else if (expandedIdx !== null && expandedIdx > idx) setExpandedIdx(expandedIdx - 1);
  }

  function handleFieldChange(idx: number, field: keyof Voice, value: string) {
    onChange(voices.map((v, i) => (i === idx ? { ...v, [field]: value } : v)));
  }

  function handleAddConfirm() {
    if (!newVoice.voice_id) return;
    onChange([...voices, { ...newVoice }]);
    setNewVoice(EMPTY_VOICE);
    setAddingRow(false);
  }

  return (
    <div className="space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-muted">
          {t("voices.label")}
        </span>
        <button
          type="button"
          onClick={handleDiscover}
          disabled={discovering || !baseUrl}
          className="text-xs px-2.5 py-1 rounded-md border border-border hover:border-kb disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {discovering ? t("voices.discovering") : t("voices.discover")}
        </button>
      </div>

      {/* Voices endpoint path */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted whitespace-nowrap shrink-0">
          {t("voices.voicesPathLabel")}
        </label>
        <input
          type="text"
          value={voicesPath}
          onChange={(e) => onVoicesPathChange(e.target.value)}
          placeholder="/v1/audio/voices"
          spellCheck={false}
          className="flex-1 text-xs px-2 py-1 border border-border rounded font-mono focus:outline-none focus:border-kb"
        />
      </div>

      {discoverError && (
        <p className="text-xs text-destructive">{discoverError}</p>
      )}

      {/* Accordion voice list */}
      {voices.length > 0 && (
        <div className="border border-border rounded-md divide-y divide-border overflow-hidden">
          {voices.map((v, i) => {
            const isOpen = expandedIdx === i;
            return (
              <div key={i}>
                {/* Collapsed summary row */}
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setExpandedIdx(isOpen ? null : i)}
                  onKeyDown={(e) => e.key === "Enter" && setExpandedIdx(isOpen ? null : i)}
                  className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-surface/50 select-none"
                >
                  <span className={`text-xs font-mono flex-1 truncate ${!v.voice_id ? "text-muted-soft italic" : ""}`}>
                    {v.voice_id || "—"}
                  </span>
                  {v.name && (
                    <span className="text-xs text-muted-soft truncate max-w-[6rem]">{v.name}</span>
                  )}
                  {v.language && (
                    <span className="text-3xs text-muted bg-surface border border-border px-1.5 py-0.5 rounded font-mono shrink-0">
                      {v.language}
                    </span>
                  )}
                  {providerId != null && v.voice_id && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        playFromApi(
                          `${v.voice_id}-${v.language}`,
                          `/api/tts/providers/${providerId}/preview`,
                          v.voice_id,
                        );
                      }}
                      className="w-6 h-6 rounded flex items-center justify-center shrink-0 text-muted-soft hover:text-kb hover:bg-surface transition-colors"
                      aria-label={playingId === `${v.voice_id}-${v.language}` ? t("voices.stop") : t("voices.play")}
                    >
                      {loadingId === `${v.voice_id}-${v.language}` ? (
                        <Spinner size="xs" />
                      ) : playingId === `${v.voice_id}-${v.language}` ? (
                        <Stop size={12} weight="fill" />
                      ) : (
                        <Play size={12} weight="fill" />
                      )}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); handleRemove(i); }}
                    className="text-muted-soft hover:text-destructive shrink-0 leading-none"
                    aria-label={t("voices.remove")}
                  >
                    ✕
                  </button>
                  <span className="text-muted-soft text-3xs shrink-0">{isOpen ? "▲" : "▼"}</span>
                </div>

                {/* Expanded edit fields */}
                {isOpen && (
                  <div className="px-3 pb-3 pt-2 grid grid-cols-2 gap-2 bg-surface/30 border-t border-border">
                    <div className="space-y-1">
                      <label className="text-3xs text-muted uppercase tracking-wide">
                        {t("voices.colVoiceId")} *
                      </label>
                      <input
                        value={v.voice_id}
                        onChange={(e) => handleFieldChange(i, "voice_id", e.target.value)}
                        placeholder="alloy"
                        className="w-full text-xs px-2 py-1 border border-border rounded font-mono focus:outline-none focus:border-kb"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-3xs text-muted uppercase tracking-wide">
                        {t("voices.colName")}
                      </label>
                      <input
                        value={v.name}
                        onChange={(e) => handleFieldChange(i, "name", e.target.value)}
                        placeholder="Alloy"
                        className="w-full text-xs px-2 py-1 border border-border rounded focus:outline-none focus:border-kb"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-3xs text-muted uppercase tracking-wide">
                        {t("voices.colLang")}
                      </label>
                      <input
                        value={v.language}
                        onChange={(e) => handleFieldChange(i, "language", e.target.value)}
                        placeholder="de"
                        className="w-full text-xs px-2 py-1 border border-border rounded font-mono focus:outline-none focus:border-kb"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-3xs text-muted uppercase tracking-wide">
                        {t("voices.colDesc")}
                      </label>
                      <input
                        value={v.description ?? ""}
                        onChange={(e) => handleFieldChange(i, "description", e.target.value)}
                        className="w-full text-xs px-2 py-1 border border-border rounded focus:outline-none focus:border-kb"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add voice form */}
      {addingRow ? (
        <div className="border border-border rounded-md p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-3xs text-muted uppercase tracking-wide">
                {t("voices.colVoiceId")} *
              </label>
              <input
                value={newVoice.voice_id}
                onChange={(e) => setNewVoice({ ...newVoice, voice_id: e.target.value })}
                placeholder="alloy"
                autoFocus
                className="w-full text-xs px-2 py-1 border border-border rounded font-mono focus:outline-none focus:border-kb"
              />
            </div>
            <div className="space-y-1">
              <label className="text-3xs text-muted uppercase tracking-wide">
                {t("voices.colName")}
              </label>
              <input
                value={newVoice.name}
                onChange={(e) => setNewVoice({ ...newVoice, name: e.target.value })}
                placeholder="Alloy"
                className="w-full text-xs px-2 py-1 border border-border rounded focus:outline-none focus:border-kb"
              />
            </div>
            <div className="space-y-1">
              <label className="text-3xs text-muted uppercase tracking-wide">
                {t("voices.colLang")}
              </label>
              <input
                value={newVoice.language}
                onChange={(e) => setNewVoice({ ...newVoice, language: e.target.value })}
                placeholder="de"
                className="w-full text-xs px-2 py-1 border border-border rounded font-mono focus:outline-none focus:border-kb"
              />
            </div>
            <div className="space-y-1">
              <label className="text-3xs text-muted uppercase tracking-wide">
                {t("voices.colDesc")}
              </label>
              <input
                value={newVoice.description ?? ""}
                onChange={(e) => setNewVoice({ ...newVoice, description: e.target.value })}
                className="w-full text-xs px-2 py-1 border border-border rounded focus:outline-none focus:border-kb"
              />
            </div>
          </div>
          <p className="text-3xs text-muted-soft">{t("voices.langHint")}</p>
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={handleAddConfirm}
              disabled={!newVoice.voice_id}
              className="text-xs px-3 py-1.5 rounded-md btn-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("voices.add")}
            </button>
            <button
              type="button"
              onClick={() => { setAddingRow(false); setNewVoice(EMPTY_VOICE); }}
              className="text-xs px-3 py-1.5 rounded-md border border-border hover:border-kb"
            >
              {t("voices.cancel")}
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAddingRow(true)}
          className="text-xs text-muted-soft hover:text-foreground transition-colors"
        >
          + {t("voices.addManual")}
        </button>
      )}
    </div>
  );
}
