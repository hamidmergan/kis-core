"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type { Voice } from "./_types";
import { discoverVoices } from "./_api";

interface Props {
  voices: Voice[];
  onChange: (voices: Voice[]) => void;
  baseUrl: string;
  apiKey?: string | null;
}

const EMPTY_VOICE: Voice = { voice_id: "", name: "", language: "", description: "" };

export function VoicesEditor({ voices, onChange, baseUrl, apiKey }: Props) {
  const t = useTranslations("admin.providers");
  const [discovering, setDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState<string | null>(null);
  const [addingRow, setAddingRow] = useState(false);
  const [newVoice, setNewVoice] = useState<Voice>(EMPTY_VOICE);

  async function handleDiscover() {
    if (!baseUrl) return;
    setDiscovering(true);
    setDiscoverError(null);
    try {
      const result = await discoverVoices(baseUrl, apiKey);
      if (!result.discoverable || result.voices.length === 0) {
        setDiscoverError(t("voices.notDiscoverable"));
        return;
      }
      // Merge: add only voices not already in the list (by voice_id)
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
  }

  function handleFieldChange(idx: number, field: keyof Voice, value: string) {
    onChange(voices.map((v, i) => (i === idx ? { ...v, [field]: value } : v)));
  }

  function handleAddConfirm() {
    if (!newVoice.voice_id || !newVoice.language) return;
    onChange([...voices, { ...newVoice }]);
    setNewVoice(EMPTY_VOICE);
    setAddingRow(false);
  }

  return (
    <div className="space-y-2">
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

      {discoverError && (
        <p className="text-xs text-destructive">{discoverError}</p>
      )}

      {voices.length > 0 && (
        <div className="border border-border rounded-md overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-muted/40">
              <tr>
                <th className="text-left px-2 py-1.5 text-muted font-medium w-[30%]">
                  {t("voices.colVoiceId")}
                </th>
                <th className="text-left px-2 py-1.5 text-muted font-medium w-[25%]">
                  {t("voices.colName")}
                </th>
                <th className="text-left px-2 py-1.5 text-muted font-medium w-[15%]">
                  {t("voices.colLang")}
                </th>
                <th className="text-left px-2 py-1.5 text-muted font-medium w-[25%]">
                  {t("voices.colDesc")}
                </th>
                <th className="w-[5%]" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {voices.map((v, i) => (
                <tr key={i} className="group">
                  <td className="px-2 py-1">
                    <input
                      value={v.voice_id}
                      onChange={(e) => handleFieldChange(i, "voice_id", e.target.value)}
                      className="w-full bg-transparent focus:outline-none font-mono"
                      placeholder="alloy"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={v.name}
                      onChange={(e) => handleFieldChange(i, "name", e.target.value)}
                      className="w-full bg-transparent focus:outline-none"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={v.language}
                      onChange={(e) => handleFieldChange(i, "language", e.target.value)}
                      className={`w-full bg-transparent focus:outline-none font-mono ${
                        !v.language ? "border-b border-destructive" : ""
                      }`}
                      placeholder="de"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={v.description ?? ""}
                      onChange={(e) => handleFieldChange(i, "description", e.target.value)}
                      className="w-full bg-transparent focus:outline-none text-muted-soft"
                    />
                  </td>
                  <td className="px-2 py-1 text-center">
                    <button
                      type="button"
                      onClick={() => handleRemove(i)}
                      className="opacity-0 group-hover:opacity-100 text-muted-soft hover:text-destructive transition-opacity"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {voices.some((v) => !v.language) && (
        <p className="text-xs text-destructive">{t("voices.languageRequired")}</p>
      )}

      {addingRow ? (
        <div className="flex gap-2 items-end border border-border rounded-md p-2">
          <div className="flex-1 space-y-1">
            <label className="text-[10px] text-muted uppercase tracking-wide">
              {t("voices.colVoiceId")} *
            </label>
            <input
              value={newVoice.voice_id}
              onChange={(e) => setNewVoice({ ...newVoice, voice_id: e.target.value })}
              placeholder="alloy"
              className="w-full text-xs px-2 py-1 border border-border rounded font-mono focus:outline-none focus:border-kb"
            />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-[10px] text-muted uppercase tracking-wide">
              {t("voices.colName")}
            </label>
            <input
              value={newVoice.name}
              onChange={(e) => setNewVoice({ ...newVoice, name: e.target.value })}
              placeholder="Alloy"
              className="w-full text-xs px-2 py-1 border border-border rounded focus:outline-none focus:border-kb"
            />
          </div>
          <div className="w-20 space-y-1">
            <label className="text-[10px] text-muted uppercase tracking-wide">
              {t("voices.colLang")} *
            </label>
            <input
              value={newVoice.language}
              onChange={(e) => setNewVoice({ ...newVoice, language: e.target.value })}
              placeholder="de"
              className="w-full text-xs px-2 py-1 border border-border rounded font-mono focus:outline-none focus:border-kb"
            />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-[10px] text-muted uppercase tracking-wide">
              {t("voices.colDesc")}
            </label>
            <input
              value={newVoice.description ?? ""}
              onChange={(e) => setNewVoice({ ...newVoice, description: e.target.value })}
              className="w-full text-xs px-2 py-1 border border-border rounded focus:outline-none focus:border-kb"
            />
          </div>
          <button
            type="button"
            onClick={handleAddConfirm}
            disabled={!newVoice.voice_id || !newVoice.language}
            className="text-xs px-3 py-1.5 rounded-md bg-kb text-white disabled:opacity-50 disabled:cursor-not-allowed"
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
