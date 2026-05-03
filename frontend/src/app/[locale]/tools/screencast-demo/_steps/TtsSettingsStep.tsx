"use client";

import { useFormatter, useTranslations } from "next-intl";
import { translateDesc } from "@/lib/voice-labels";
import type { SlideData } from "@/types";
import Select from "@/components/ui/Select";


interface Voice {
  voice_id: string;
  label: string;
  description?: string | null;
}

type TtsProvider = "elevenlabs" | "kokoro" | "mylab";


interface TtsSettingsStepProps {
  providersLoaded: boolean;
  elevenlabsEnabled: boolean;
  kokoroEnabled: boolean;
  mylabEnabled: boolean;
  ttsProvider: TtsProvider;
  voices: Voice[];
  kokoroVoices: Array<{ voice_id: string; name: string; accent: string; gender: string }>;
  mylabVoices: Array<{ voice_id: string; name: string; description: string }>;
  voiceId: string;
  speed: number;
  slidePause: number;
  dpi: number;
  slides: SlideData[];
  totalWords: number;
  totalChars: number;
  scriptOverLimit: boolean;
  maxChars: number;
  ttsSettingsError: string;
  onTtsProviderChange: (p: TtsProvider) => void;
  onVoiceIdChange: (id: string) => void;
  onSpeedChange: (v: number) => void;
  onSlidePauseChange: (v: number) => void;
  onDpiChange: (v: number) => void;
  onBackToScripts: () => void;
  onStartRender: () => void;
}


export function TtsSettingsStep({
  providersLoaded, elevenlabsEnabled, kokoroEnabled, mylabEnabled,
  ttsProvider, voices, kokoroVoices, mylabVoices, voiceId,
  speed, slidePause, dpi, slides, totalWords, totalChars, scriptOverLimit, maxChars, ttsSettingsError,
  onTtsProviderChange, onVoiceIdChange, onSpeedChange, onSlidePauseChange, onDpiChange,
  onBackToScripts, onStartRender,
}: TtsSettingsStepProps) {
  const t = useTranslations("tools.screencast");
  const format = useFormatter();
  const charsText = format.number(totalChars);
  const maxText = format.number(maxChars);

  const handleProviderChange = (p: TtsProvider) => {
    onTtsProviderChange(p);
    if (p === "kokoro" && kokoroVoices.length > 0) onVoiceIdChange(kokoroVoices[0].voice_id);
    else if (p === "mylab" && mylabVoices.length > 0) onVoiceIdChange(mylabVoices[0].voice_id);
    else if (p === "elevenlabs" && voices.length > 0) onVoiceIdChange(voices[0].voice_id);
  };

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-6">{t("ttsSettings.heading")}</h2>

      {providersLoaded && (elevenlabsEnabled || kokoroEnabled || mylabEnabled) && (
        <div className="mb-2">
          <label htmlFor="sc-provider-select" className="block text-sm font-medium text-foreground-soft mb-2">{t("ttsSettings.providerLabel")}</label>
          <Select id="sc-provider-select" value={ttsProvider}
            onChange={(v) => handleProviderChange(v as TtsProvider)}
            options={[
              ...(kokoroEnabled ? [{ value: "kokoro", label: "Kokoro TTS" }] : []),
              ...(mylabEnabled ? [{ value: "mylab", label: "THL myLab (XTTS-v2)" }] : []),
              ...(elevenlabsEnabled ? [{ value: "elevenlabs", label: "ElevenLabs" }] : []),
            ]}
          />
        </div>
      )}

      {providersLoaded && (elevenlabsEnabled || kokoroEnabled || mylabEnabled) && (
        <div className="mb-6 mt-4 space-y-3">
          <div>
            <label htmlFor="sc-voice-select" className="block text-sm font-medium text-foreground-soft mb-2">{t("ttsSettings.voiceLabel")}</label>
            <Select id="sc-voice-select" value={voiceId} onChange={onVoiceIdChange}
              options={
                ttsProvider === "kokoro"
                  ? kokoroVoices.map((v) => {
                      const flag = v.accent === "American" ? "🇺🇸" : v.accent === "British" ? "🇬🇧" : "";
                      return { value: v.voice_id, label: `${flag} ${v.name}`.trim() };
                    })
                  : ttsProvider === "mylab"
                  ? mylabVoices.map((v) => ({ value: v.voice_id, label: `${v.name} - ${v.description}` }))
                  : voices.map((v) => {
                      const desc = translateDesc(v.description);
                      return { value: v.voice_id, label: desc ? `${v.label} - ${desc}` : v.label };
                    })
              }
            />
          </div>
          {ttsProvider === "elevenlabs" && (
            <a href="/tools/tts/voices" target="_blank" rel="noopener noreferrer" className="text-sm text-kb hover:underline">{t("ttsSettings.previewVoices")}</a>
          )}
          {ttsProvider === "kokoro" && (
            <a href="/tools/tts/voices?tab=kokoro" target="_blank" rel="noopener noreferrer" className="text-sm text-kb hover:underline">{t("ttsSettings.previewVoices")}</a>
          )}
          {ttsProvider === "mylab" && (
            <a href="/tools/tts/voices?tab=mylab" target="_blank" rel="noopener noreferrer" className="text-sm text-kb hover:underline">{t("ttsSettings.previewVoices")}</a>
          )}
        </div>
      )}

      <div className="mb-6">
        <label htmlFor="speed-slider" className="block text-sm font-medium text-foreground-soft mb-2">{t("ttsSettings.speed", { speed: speed.toFixed(1) })}</label>
        <input id="speed-slider" type="range" min="0.7" max="1.2" step="0.1" value={speed}
          onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-surface-dim rounded-lg appearance-none cursor-pointer accent-kb" />
        <div className="flex justify-between text-xs text-muted-soft mt-1">
          <span>{t("ttsSettings.speedSlow")}</span><span>{t("ttsSettings.speedFast")}</span>
        </div>
        <p className="text-xs text-muted-soft mt-2">{t("ttsSettings.speedHint")}</p>
      </div>

      <div className="mb-6">
        <label className="block text-sm font-medium text-foreground-soft mb-2">{t("ttsSettings.slidePause", { seconds: slidePause.toFixed(1) })}</label>
        <input type="range" min={0} max={3} step={0.1} value={slidePause}
          onChange={(e) => onSlidePauseChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-surface-dim rounded-lg appearance-none cursor-pointer accent-kb" />
        <div className="flex justify-between text-xs text-muted-soft mt-1"><span>{t("ttsSettings.slidePauseMin")}</span><span>{t("ttsSettings.slidePauseMax")}</span></div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground-soft">{t("ttsSettings.imageQuality")}</p>
        <div className="flex flex-col gap-2">
          {[{ val: 96, label: t("ttsSettings.qualityLow"), desc: t("ttsSettings.qualityLowDesc") },
            { val: 144, label: t("ttsSettings.qualityStandard"), desc: t("ttsSettings.qualityStandardDesc") },
            { val: 300, label: t("ttsSettings.qualityHigh"), desc: t("ttsSettings.qualityHighDesc") }
          ].map(({ val, label, desc }) => (
            <label key={val} className="flex items-start gap-3 cursor-pointer">
              <input type="radio" name="dpi" value={val} checked={dpi === val} onChange={() => onDpiChange(val)}
                className="mt-0.5 h-4 w-4 text-kb focus:ring-kb" />
              <div>
                <span className="text-sm font-medium text-foreground-soft">{label}</span>
                <p className="text-xs text-muted-soft mt-0.5">{desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="mt-4 mb-4 rounded-lg bg-surface px-4 py-3">
        <p className="text-sm text-foreground-soft">
          {t.rich("ttsSettings.summary", {
            bold: (chunks) => <span className="font-medium">{chunks}</span>,
            charsTag: (chunks) => <span className={`font-medium ${scriptOverLimit ? "text-error" : ""}`}>{chunks}</span>,
            slides: slides.length,
            words: totalWords,
            chars: charsText,
            max: maxText,
          })}
        </p>
      </div>

      {scriptOverLimit && (
        <div className="mb-4 rounded-lg border border-error-border bg-error-bg px-4 py-3 flex items-start gap-3">
          <span className="text-error mt-0.5">⚠</span>
          <div className="flex-1">
            <p className="text-sm font-medium text-error-strong">{t("ttsSettings.scriptTooLong")}</p>
            <p className="text-sm text-error mt-0.5">
              {t("ttsSettings.scriptTooLongBody", { chars: charsText, max: maxText })}
            </p>
            <button onClick={onBackToScripts} className="mt-2 px-3 py-1.5 text-sm font-medium text-error-strong border border-error-border rounded-md hover:bg-error-bg transition-colors">
              {t("ttsSettings.backToEdit")}
            </button>
          </div>
        </div>
      )}

      {ttsSettingsError && (
        <p className="text-sm text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2 mb-3">{ttsSettingsError}</p>
      )}

      <div className="flex gap-3">
        <button onClick={onBackToScripts} className="px-4 py-3 text-sm text-foreground-soft border-2 border-border rounded-md hover:border-kb transition-colors">{t("ttsSettings.back")}</button>
        <button onClick={onStartRender} disabled={scriptOverLimit}
          className="flex-1 px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
          {t("ttsSettings.startRender")}
        </button>
      </div>
    </section>
  );
}
