"use client";

import { useEffect, useState } from "react";
import PlayButton from "../_components/PlayButton";
import { useVoicePlayer } from "../_hooks/useVoicePlayer";
import type { MylabVoice } from "../_utils";


export default function MylabTab({ active }: { active: boolean }) {
  const [voices, setVoices] = useState<MylabVoice[]>([]);
  const [loading, setLoading] = useState(false);
  const { playingId, loadingId, playFromApi } = useVoicePlayer();

  useEffect(() => {
    if (!active || voices.length > 0) return;
    setLoading(true);
    fetch("/api/mylab/voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setVoices(data.voices ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [active, voices.length]);

  if (loading) return <p className="text-sm text-gray-500">Wird geladen…</p>;
  if (voices.length === 0) {
    return <p className="text-sm text-gray-400">myLab TTS Server nicht erreichbar oder keine Stimmen gefunden.</p>;
  }

  return (
    <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
      {voices.map((voice) => (
        <div key={voice.voice_id} className="flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-100">
          <div>
            <p className="text-sm font-medium text-gray-900">{voice.name}</p>
            <p className="text-xs text-gray-400 mt-0.5">{voice.description}</p>
          </div>
          <PlayButton
            voiceId={voice.voice_id}
            playingId={playingId}
            loadingId={loadingId}
            onClick={() => playFromApi(voice.voice_id, "/api/mylab/preview")}
          />
        </div>
      ))}
    </div>
  );
}
