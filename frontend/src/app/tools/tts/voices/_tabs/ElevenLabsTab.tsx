"use client";

import { useEffect, useState } from "react";
import PlayButton from "../_components/PlayButton";
import { useVoicePlayer } from "../_hooks/useVoicePlayer";
import { CATEGORY_DE, translateLabel, type Voice } from "../_utils";


export default function ElevenLabsTab({ enabled }: { enabled: boolean }) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const { playingId, loadingId, playUrl } = useVoicePlayer();

  useEffect(() => {
    if (!enabled) { setLoading(false); return; }
    fetch("/api/voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setVoices(data.voices ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [enabled]);

  if (loading) return <p className="text-sm text-muted">Wird geladen…</p>;
  if (voices.length === 0) return <p className="text-sm text-muted">Keine Stimmen verfügbar.</p>;

  return (
    <div className="divide-y divide-border-soft border border-border-soft rounded-lg overflow-hidden">
      {voices.map((voice) => {
        const labelParts: string[] = [];
        if (voice.category && CATEGORY_DE[voice.category]) labelParts.push(CATEGORY_DE[voice.category]);
        const desc = translateLabel(voice.description, voice.use_case);
        if (desc) labelParts.push(desc);

        return (
          <div key={voice.voice_id} className="flex items-center justify-between px-4 py-3 bg-white hover:bg-surface">
            <div>
              <p className="text-sm font-medium text-foreground">{voice.label.split(" - ")[0]}</p>
              {labelParts.length > 0 && (
                <p className="text-xs text-muted-soft mt-0.5">{labelParts.join(" · ")}</p>
              )}
            </div>
            {voice.preview_url ? (
              <PlayButton
                voiceId={voice.voice_id}
                playingId={playingId}
                loadingId={loadingId}
                onClick={() => playUrl(voice.voice_id, voice.preview_url!)}
              />
            ) : (
              <span className="text-xs text-muted-soft">Kein Sample</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
