"use client";

import { useFormatter, useTranslations } from "next-intl";
import type { SlideData } from "@/types";
import type { ProviderWithVoices } from "@/hooks/useVoices";
import OwnVoicesLink from "@/components/OwnVoicesLink";
import Select from "@/components/ui/Select";
import ProviderAvailabilityHint from "@/components/tools/ProviderAvailabilityHint";
import Checkbox from "@/components/ui/Checkbox";
import { LANGUAGE_FLAG } from "@/lib/languageFlags";
import StepFooter from "./StepFooter";
import FolienAuswahl from "./FolienAuswahl";
import type { VertonterStand } from "../_utils";

interface TtsSettingsStepProps {
  onBack: (() => void) | null;
  providersLoaded: boolean;
  providers: ProviderWithVoices[];
  providerId: number;
  voiceId: string;
  slidePause: number;
  subtitles: boolean;
  slides: SlideData[];
  totalWords: number;
  totalChars: number;
  scriptOverLimit: boolean;
  maxChars: number;
  ttsSettingsError: string;
  stand: VertonterStand | null;
  imScreencast: number[];
  neuVertonen: number[];
  ohneTon: Set<number>;
  geaenderteOhneHaken: number;
  zeigtNeu: boolean;
  stimmeGewechselt: boolean;
  onUmschaltenScreencast: (i: number) => void;
  onUmschaltenNeu: (i: number) => void;
  onAlleFolien: (zeigtNeu: boolean) => void;
  onKeineFolien: (zeigtNeu: boolean) => void;
  onGeaenderteFolien: () => void;
  onProviderIdChange: (id: number) => void;
  onVoiceIdChange: (v: string) => void;
  onSlidePauseChange: (v: number) => void;
  onSubtitlesChange: (v: boolean) => void;
  onBackToScripts: () => void;
  onStartRender: () => void;
  laufUmsonst: boolean;
  stimmwechselWirkungslos: boolean;
  onZumVideo: () => void;
}

export default function TtsSettingsStep(props: TtsSettingsStepProps) {
  const {
    onBack,
    providersLoaded,
    providers,
    providerId,
    voiceId,
    slidePause,
    subtitles,
    slides,
    totalWords,
    totalChars,
    scriptOverLimit,
    maxChars,
    ttsSettingsError,
    stand,
    imScreencast,
    neuVertonen,
    ohneTon,
    geaenderteOhneHaken,
    zeigtNeu,
    stimmeGewechselt,
    onUmschaltenScreencast,
    onUmschaltenNeu,
    onAlleFolien,
    onKeineFolien,
    onGeaenderteFolien,
    onProviderIdChange,
    onVoiceIdChange,
    onSlidePauseChange,
    onSubtitlesChange,
    onBackToScripts,
    onStartRender,
    laufUmsonst,
    stimmwechselWirkungslos,
    onZumVideo,
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
            <ProviderAvailabilityHint />
          </div>
          <div className="flex flex-col items-start gap-1">
            <a
              href="/tools/tts/voices"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-kb hover:underline"
            >
              {t("ttsSettings.previewVoices")}
            </a>
            <OwnVoicesLink />
          </div>
        </div>
      )}

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

      <FolienAuswahl
        slides={slides}
        stand={stand}
        imScreencast={imScreencast}
        neuVertonen={neuVertonen}
        ohneTon={ohneTon}
        zeigtNeu={zeigtNeu}
        stimmeGewechselt={stimmeGewechselt}
        onUmschaltenScreencast={onUmschaltenScreencast}
        onUmschaltenNeu={onUmschaltenNeu}
        onAlle={onAlleFolien}
        onKeine={onKeineFolien}
        onGeaenderte={onGeaenderteFolien}
      />

      <div className="mt-4 mb-4 rounded-lg bg-surface px-4 py-3">
        <p className="text-sm text-foreground-soft">
          {t.rich("ttsSettings.summary", {
            bold: (chunks) => <span className="font-medium">{chunks}</span>,
            charsTag: (chunks) => <span className={`font-medium ${scriptOverLimit ? "text-error" : ""}`}>{chunks}</span>,
            slides: imScreencast.length,
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
      {geaenderteOhneHaken > 0 && (
        <p className="mb-3 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="status">
          {t("folienAuswahl.geaendertBehaeltAltenTon", { n: geaenderteOhneHaken })}
        </p>
      )}
      {imScreencast.length === 0 && (
        <p className="mb-3 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
          {t("folienAuswahl.keineFolie")}
        </p>
      )}
      {laufUmsonst && (
        <p className="mb-3 rounded-lg bg-surface px-4 py-3 text-sm text-foreground-soft" role="status">
          {t("ttsSettings.nichtsGeaendert")}
        </p>
      )}
      {stimmwechselWirkungslos && (
        <p className="mb-3 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
          {t("ttsSettings.stimmwechselOhneHaken")}
        </p>
      )}
      <StepFooter
        onBack={onBack}
        nextLabel={laufUmsonst ? t("ttsSettings.zumFertigenVideo") : t("ttsSettings.startRender")}
        onNext={laufUmsonst ? onZumVideo : onStartRender}
        nextDisabled={scriptOverLimit || imScreencast.length === 0 || stimmwechselWirkungslos}
      />
    </section>
  );
}
