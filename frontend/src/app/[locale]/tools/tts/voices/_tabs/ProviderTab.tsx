"use client";

import { useTranslations } from "next-intl";
import PlayButton from "../_components/PlayButton";
import { useVoicePlayer } from "../_hooks/useVoicePlayer";
import { LANGUAGE_LABEL, UNIVERSAL_LANG, type Voice } from "../_utils";


interface Props {
  providerId: number;
  voices: Voice[];
}


export default function ProviderTab({ providerId, voices }: Props) {
  const t = useTranslations("tools.tts.voices");
  const { playingId, loadingId, playFromApi } = useVoicePlayer();

  if (voices.length === 0) {
    return <p className="text-sm text-muted-soft">{t("noVoices")}</p>;
  }

  // Group by language; empty language → "universal" bucket
  const grouped: Record<string, Voice[]> = {};
  for (const v of voices) {
    const lang = v.language || UNIVERSAL_LANG;
    if (!grouped[lang]) grouped[lang] = [];
    grouped[lang].push(v);
  }
  // Specific languages first (alphabetical), universal bucket last
  const languages = Object.keys(grouped).sort((a, b) => {
    if (a === UNIVERSAL_LANG) return 1;
    if (b === UNIVERSAL_LANG) return -1;
    return a.localeCompare(b);
  });

  return (
    <div className="space-y-4">
      {languages.map((lang) => (
        <details key={lang} open={lang === "de" || lang === UNIVERSAL_LANG || languages.length === 1}>
          <summary className="cursor-pointer select-none px-4 py-3 bg-surface border border-border-soft rounded-lg text-sm font-medium text-foreground hover:bg-surface transition-colors">
            {LANGUAGE_LABEL[lang] ?? lang}
            <span className="ml-2 text-xs text-muted-soft font-normal">
              {grouped[lang].length} {grouped[lang].length === 1 ? t("voiceSingular") : t("voicePlural")}
            </span>
          </summary>
          <div className="mt-1 divide-y divide-border-soft border border-border-soft rounded-lg overflow-hidden">
            {grouped[lang].map((voice) => (
              <div
                key={`${voice.voice_id}-${voice.language}`}
                className="flex items-center justify-between px-4 py-3 bg-background hover:bg-surface"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{voice.name}</p>
                  {voice.description && (
                    <p className="text-xs text-muted-soft mt-0.5">{voice.description}</p>
                  )}
                </div>
                <PlayButton
                  voiceId={`${voice.voice_id}-${voice.language}`}
                  playingId={playingId}
                  loadingId={loadingId}
                  onClick={() =>
                    playFromApi(
                      `${voice.voice_id}-${voice.language}`,
                      `/api/tts/providers/${providerId}/preview`,
                      voice.voice_id,
                    )
                  }
                />
              </div>
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}
