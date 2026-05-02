"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import PlayButton from "../_components/PlayButton";
import { useVoicePlayer } from "../_hooks/useVoicePlayer";
import type { OpenAITtsVoice } from "../_utils";


export default function MylabTab({ active }: { active: boolean }) {
  const t = useTranslations("tools.tts.voices");
  const [voices, setVoices] = useState<OpenAITtsVoice[]>([]);
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

  if (loading) return <p className="text-sm text-muted">{t("loading")}</p>;
  if (voices.length === 0) {
    return <p className="text-sm text-muted-soft">{t("mylabUnavailable")}</p>;
  }

  return (
    <div className="divide-y divide-border-soft border border-border-soft rounded-lg overflow-hidden">
      {voices.map((voice) => (
        <div key={voice.voice_id} className="flex items-center justify-between px-4 py-3 bg-background hover:bg-surface">
          <div>
            <p className="text-sm font-medium text-foreground">{voice.name}</p>
            <p className="text-xs text-muted-soft mt-0.5">{voice.description}</p>
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
