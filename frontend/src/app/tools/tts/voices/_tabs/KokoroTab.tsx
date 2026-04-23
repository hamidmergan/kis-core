"use client";

import { useEffect, useState } from "react";
import PlayButton from "../_components/PlayButton";
import { useVoicePlayer } from "../_hooks/useVoicePlayer";
import { KOKORO_LANGUAGE_LABEL, KOKORO_LANGUAGE_ORDER, type KokoroVoice } from "../_utils";


export default function KokoroTab({ active }: { active: boolean }) {
  const [voices, setVoices] = useState<KokoroVoice[]>([]);
  const [loading, setLoading] = useState(false);
  const { playingId, loadingId, playFromApi } = useVoicePlayer();

  useEffect(() => {
    if (!active || voices.length > 0) return;
    setLoading(true);
    fetch("/api/kokoro/voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setVoices(data.voices ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [active, voices.length]);

  if (loading) return <p className="text-sm text-gray-500">Wird geladen…</p>;
  if (voices.length === 0) {
    return <p className="text-sm text-gray-400">Kokoro Server nicht erreichbar oder keine Stimmen gefunden.</p>;
  }

  const grouped: Record<string, KokoroVoice[]> = {};
  for (const v of voices) {
    const lang = v.language || (v.accent === "American" || v.accent === "British" ? "English" : v.accent);
    if (!grouped[lang]) grouped[lang] = [];
    grouped[lang].push(v);
  }
  const languages = KOKORO_LANGUAGE_ORDER.filter(l => grouped[l]);
  for (const l of Object.keys(grouped)) {
    if (!languages.includes(l)) languages.push(l);
  }

  return (
    <div className="space-y-4">
      {languages.map((lang) => (
        <details key={lang} open={lang === "Deutsch"}>
          <summary className="cursor-pointer select-none px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg text-sm font-medium text-gray-800 hover:bg-gray-100 transition-colors">
            {KOKORO_LANGUAGE_LABEL[lang] ?? lang}
            <span className="ml-2 text-xs text-gray-400 font-normal">
              {grouped[lang].length} {grouped[lang].length === 1 ? "Stimme" : "Stimmen"}
            </span>
          </summary>
          <div className="mt-1 divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
            {grouped[lang].map((voice) => (
              <div key={voice.voice_id} className="flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50">
                <div>
                  <p className="text-sm font-medium text-gray-900">{voice.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {voice.gender === "Female" ? "Weiblich" : "Männlich"}
                    {voice.accent && lang === "English" ? ` · ${voice.accent}` : ""}
                  </p>
                </div>
                <PlayButton
                  voiceId={voice.voice_id}
                  playingId={playingId}
                  loadingId={loadingId}
                  onClick={() => playFromApi(voice.voice_id, "/api/kokoro/preview")}
                />
              </div>
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}
