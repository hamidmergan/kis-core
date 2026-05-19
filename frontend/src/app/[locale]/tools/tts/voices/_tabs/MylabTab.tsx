"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import PlayButton from "../_components/PlayButton";
import { useVoicePlayer } from "../_hooks/useVoicePlayer";
import { MYLAB_LANGUAGE_LABEL, MYLAB_LANGUAGE_ORDER, type OpenAITtsVoice } from "../_utils";


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

  const grouped: Record<string, OpenAITtsVoice[]> = {};
  for (const v of voices) {
    const lang = v.language ?? "other";
    if (!grouped[lang]) grouped[lang] = [];
    grouped[lang].push(v);
  }
  const languages = MYLAB_LANGUAGE_ORDER.filter((l) => grouped[l]);
  for (const l of Object.keys(grouped)) {
    if (!languages.includes(l)) languages.push(l);
  }

  return (
    <div className="space-y-4">
      {languages.map((lang) => (
        <details key={lang} open={lang === "de"}>
          <summary className="cursor-pointer select-none px-4 py-3 bg-surface border border-border-soft rounded-lg text-sm font-medium text-foreground hover:bg-surface transition-colors">
            {MYLAB_LANGUAGE_LABEL[lang] ?? lang}
            <span className="ml-2 text-xs text-muted-soft font-normal">
              {grouped[lang].length} {grouped[lang].length === 1 ? t("voiceSingular") : t("voicePlural")}
            </span>
          </summary>
          <div className="mt-1 divide-y divide-border-soft border border-border-soft rounded-lg overflow-hidden">
            {grouped[lang].map((voice) => (
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
        </details>
      ))}
    </div>
  );
}
