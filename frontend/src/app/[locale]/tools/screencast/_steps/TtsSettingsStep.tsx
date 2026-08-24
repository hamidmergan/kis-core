"use client";

import { useFormatter, useTranslations } from "next-intl";
import type { SlideData } from "@/types";
import type { ProviderWithVoices } from "@/hooks/useVoices";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import { LANGUAGE_FLAG } from "@/lib/languageFlags";
import StepFooter from "./StepFooter";

interface TtsSettingsStepProps {
  onBack: (() => void) | null;
  providersLoaded: boolean;
  providers: ProviderWithVoices[];
  providerId: number;
  targetLang: string;
  languages: { id: string; label: string }[];
  voiceId: string;
  speed: number;
  slidePause: number;
  dpi: number;
  subtitles: boolean;
  slides: SlideData[];
  totalWords: number;
  totalChars: number;
  scriptOverLimit: boolean;
  maxChars: number;
  ttsSettingsError: string;
  onProviderIdChange: (id: number) => void;
  onTargetLangChange: (v: string) => void;
  onVoiceIdChange: (v: string) => void;
  onSpeedChange: (v: number) => void;
  onSlidePauseChange: (v: number) => void;
  onDpiChange: (v: number) => void;
  onSubtitlesChange: (v: boolean) => void;
  onBackToScripts: () => void;
  onStartRender: () => void;
}

export default function TtsSettingsStep(props: TtsSettingsStepProps) {
  const {
    onBack,
    providersLoaded,
    providers,
    providerId,
    targetLang,
    languages,
    voiceId,
    speed,
    slidePause,
    dpi,
    subtitles,
    slides,
    totalWords,
    totalChars,
    scriptOverLimit,
    maxChars,
    ttsSettingsError,
    onProviderIdChange,
    onTargetLangChange,
    onVoiceIdChange,
    onSpeedChange,
    onSlidePauseChange,
    onDpiChange,
    onSubtitlesChange,
    onBackToScripts,
    onStartRender,
  } = props;

  const t = useTranslations("tools.screencast");
  const format = useFormatter();
  const charsText = format.number(totalChars);
  const maxText = format.number(maxChars);

  const anyProvider = providers.length > 0;
  const activeProvider = providers.find((p) => p.id === providerId);

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-6">{t("ttsSettings.heading")}</h2>

      {providersLoaded && anyProvider && (
        <div className="mb-2">
          <label htmlFor="sc-provider-select" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("ttsSettings.providerLabel")}
          </label>
          <Select
            id="sc-provider-select"
            value={String(providerId)}
            onChange={(v) => {
              const newId = Number(v);
              onProviderIdChange(newId);
              const p = providers.find((x) => x.id === newId);
              if (p && p.voices.length > 0) onVoiceIdChange(p.voices[0].voice_id);
            }}
            options={providers.map((p) => ({ value: String(p.id), label: p.name }))}
          />
        </div>
      )}

      {languages.length > 0 && (
        <div className="mb-2 mt-4">
          <label htmlFor="sc-lang-select" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("ttsSettings.langLabel")}
          </label>
          <Select
            id="sc-lang-select"
            value={targetLang}
            onChange={onTargetLangChange}
            options={languages.map((l) => ({ value: l.id, label: l.label }))}
          />
          <p className="mt-1 text-xs text-muted">{t("ttsSettings.langHint")}</p>
        </div>
      )}

      {providersLoaded && anyProvider && (
        <div className="mb-6 mt-4 space-y-3">
          <div>
            <label htmlFor="sc-voice-select" className="block text-sm font-medium text-foreground-soft mb-2">
              {t("ttsSettings.voiceLabel")}
            </label>
            <Select
              id="sc-voice-select"
              value={voiceId}
              onChange={onVoiceIdChange}
              options={(activeProvider?.voices ?? []).map((v) => ({
                value: v.voice_id,
                label: `${LANGUAGE_FLAG[v.language] ?? ""} ${v.name}${v.description ? ` — ${v.description}` : ""}`.trim(),
              }))}
            />
          </div>
          <a
            href="/tools/tts/voices"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-kb hover:underline"
          >
            {t("ttsSettings.previewVoices")}
          </a>
        </div>
      )}

      <div className="mb-6">
        <label htmlFor="speed-slider" className="block text-sm font-medium text-foreground-soft mb-2">
          {t("ttsSettings.speed", { speed: speed.toFixed(1) })}
        </label>
        <input
          id="speed-slider"
          type="range"
          min="0.7"
          max="1.2"
          step="0.1"
          value={speed}
          onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-surface-dim rounded-lg appearance-none cursor-pointer accent-kb"
        />
        <div className="flex justify-between text-xs text-muted-soft mt-1">
          <span>{t("ttsSettings.speedSlow")}</span>
          <span>{t("ttsSettings.speedFast")}</span>
        </div>
        <p className="text-xs text-muted-soft mt-2">{t("ttsSettings.speedHint")}</p>
      </div>

      <div className="mb-6">
        <label className="block text-sm font-medium text-foreground-soft mb-2">
          {t("ttsSettings.slidePause", { seconds: slidePause.toFixed(1) })}
        </label>
        <input
          type="range"
          min={0}
          max={3}
          step={0.1}
          value={slidePause}
          onChange={(e) => onSlidePauseChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-surface-dim rounded-lg appearance-none cursor-pointer accent-kb"
        />
        <div className="flex justify-between text-xs text-muted-soft mt-1">
          <span>{t("ttsSettings.slidePauseMin")}</span>
          <span>{t("ttsSettings.slidePauseMax")}</span>
        </div>
      </div>

      <div className="mb-6">
        <Checkbox
          checked={subtitles}
          onChange={onSubtitlesChange}
          label={t("ttsSettings.subtitles")}
          labelClassName="text-sm font-medium text-foreground-soft"
        />
        <p className="text-xs text-muted-soft mt-2">{t("ttsSettings.subtitlesHint")}</p>
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
            <button
              onClick={onBackToScripts}
              className="mt-2 px-3 py-1.5 text-sm font-medium text-error-strong border border-error-border rounded-md hover:bg-error-bg transition-colors"
            >
              {t("ttsSettings.backToEdit")}
            </button>
          </div>
        </div>
      )}

      {ttsSettingsError && (
        <p className="text-sm text-warn bg-warn-bg border border-warn-border rounded-md px-3 py-2 mb-3">{ttsSettingsError}</p>
      )}
      <StepFooter
        onBack={onBack}
        nextLabel={t("ttsSettings.startRender")}
        onNext={onStartRender}
        nextDisabled={scriptOverLimit}
      />
    </section>
  );
}
