"use client";

import { translateDesc } from "@/lib/voice-labels";
import type { SlideData } from "@/types";

interface ElevenLabsVoice {
  voice_id: string;
  label: string;
  description?: string | null;
  use_case?: string | null;
}
interface KokoroVoice {
  voice_id: string;
  name: string;
  accent: string;
  gender: string;
}
interface MylabVoice {
  voice_id: string;
  name: string;
  description: string;
}

type TtsProvider = "elevenlabs" | "fish_speech" | "kokoro" | "mylab";

interface TtsSettingsStepProps {
  providersLoaded: boolean;
  elevenlabsEnabled: boolean;
  fishSpeechEnabled: boolean;
  kokoroEnabled: boolean;
  mylabEnabled: boolean;
  ttsProvider: TtsProvider;
  voices: ElevenLabsVoice[];
  kokoroVoices: KokoroVoice[];
  mylabVoices: MylabVoice[];
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
  onVoiceIdChange: (v: string) => void;
  onSpeedChange: (v: number) => void;
  onSlidePauseChange: (v: number) => void;
  onDpiChange: (v: number) => void;
  onBackToScripts: () => void;
  onStartRender: () => void;
}

export default function TtsSettingsStep(props: TtsSettingsStepProps) {
  const {
    providersLoaded,
    elevenlabsEnabled,
    fishSpeechEnabled,
    kokoroEnabled,
    mylabEnabled,
    ttsProvider,
    voices,
    kokoroVoices,
    mylabVoices,
    voiceId,
    speed,
    slidePause,
    dpi,
    slides,
    totalWords,
    totalChars,
    scriptOverLimit,
    maxChars,
    ttsSettingsError,
    onTtsProviderChange,
    onVoiceIdChange,
    onSpeedChange,
    onSlidePauseChange,
    onDpiChange,
    onBackToScripts,
    onStartRender,
  } = props;

  const anyProvider = elevenlabsEnabled || fishSpeechEnabled || kokoroEnabled || mylabEnabled;

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-6">Einstellungen</h2>

      {providersLoaded && anyProvider && (
        <div className="mb-2">
          <label htmlFor="sc-provider-select" className="block text-sm font-medium text-gray-700 mb-2">
            TTS-Anbieter
          </label>
          <select
            id="sc-provider-select"
            value={ttsProvider}
            onChange={(e) => {
              const p = e.target.value as TtsProvider;
              onTtsProviderChange(p);
              if (p === "fish_speech") onVoiceIdChange("default");
              else if (p === "kokoro" && kokoroVoices.length > 0) onVoiceIdChange(kokoroVoices[0].voice_id);
              else if (p === "mylab" && mylabVoices.length > 0) onVoiceIdChange(mylabVoices[0].voice_id);
              else if (p === "elevenlabs" && voices.length > 0) onVoiceIdChange(voices[0].voice_id);
            }}
            className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary"
          >
            {kokoroEnabled && <option value="kokoro">Kokoro TTS</option>}
            {mylabEnabled && <option value="mylab">THL myLab (XTTS-v2)</option>}
            {fishSpeechEnabled && <option value="fish_speech">Fish Speech 1.5.1</option>}
            {elevenlabsEnabled && <option value="elevenlabs">ElevenLabs</option>}
          </select>
        </div>
      )}

      {providersLoaded && anyProvider && (
        <div className="mb-6 mt-4 space-y-3">
          <div>
            <label htmlFor="sc-voice-select" className="block text-sm font-medium text-gray-700 mb-2">
              Stimme
            </label>
            <select
              id="sc-voice-select"
              value={voiceId}
              onChange={(e) => onVoiceIdChange(e.target.value)}
              disabled={ttsProvider === "fish_speech"}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {ttsProvider === "fish_speech" ? (
                <option value="default">Standard</option>
              ) : ttsProvider === "kokoro" ? (
                kokoroVoices.map((v) => {
                  const flag = v.accent === "American" ? "🇺🇸" : v.accent === "British" ? "🇬🇧" : "";
                  return (
                    <option key={v.voice_id} value={v.voice_id}>
                      {flag} {v.name}
                    </option>
                  );
                })
              ) : ttsProvider === "mylab" ? (
                mylabVoices.map((v) => (
                  <option key={v.voice_id} value={v.voice_id}>
                    {v.name} – {v.description}
                  </option>
                ))
              ) : (
                voices.map((v) => {
                  const desc = translateDesc(v.description);
                  return (
                    <option key={v.voice_id} value={v.voice_id}>
                      {desc ? `${v.label} – ${desc}` : v.label}
                    </option>
                  );
                })
              )}
            </select>
          </div>
          {ttsProvider === "elevenlabs" && (
            <a href="/tools/tts/voices" target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">
              Stimmen anhören →
            </a>
          )}
          {ttsProvider === "kokoro" && (
            <a href="/tools/tts/voices?tab=kokoro" target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">
              Stimmen anhören →
            </a>
          )}
          {ttsProvider === "mylab" && (
            <a href="/tools/tts/voices?tab=mylab" target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">
              Stimmen anhören →
            </a>
          )}
        </div>
      )}

      <div className="mb-6">
        <label htmlFor="speed-slider" className="block text-sm font-medium text-gray-700 mb-2">
          Geschwindigkeit: {speed.toFixed(1)}x
        </label>
        <input
          id="speed-slider"
          type="range"
          min="0.7"
          max="1.2"
          step="0.1"
          value={speed}
          onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
        />
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>Langsam (0.7x)</span>
          <span>Schnell (1.2x)</span>
        </div>
        <p className="text-xs text-gray-400 mt-2">Langsamere Geschwindigkeit empfohlen für Lehrvideos</p>
      </div>

      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Pause zwischen Folien: {slidePause.toFixed(1)}s</label>
        <input
          type="range"
          min={0}
          max={3}
          step={0.1}
          value={slidePause}
          onChange={(e) => onSlidePauseChange(parseFloat(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
        />
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>0s</span>
          <span>3s</span>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-gray-700">Bildqualität</p>
        <div className="flex flex-col gap-2">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              name="dpi"
              value={96}
              checked={dpi === 96}
              onChange={() => onDpiChange(96)}
              className="mt-0.5 h-4 w-4 text-primary focus:ring-primary"
            />
            <div>
              <span className="text-sm font-medium text-gray-700">Geringe Qualität</span>
              <p className="text-xs text-gray-400 mt-0.5">Schnellere Verarbeitung, geringere Bildschärfe</p>
            </div>
          </label>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              name="dpi"
              value={144}
              checked={dpi === 144}
              onChange={() => onDpiChange(144)}
              className="mt-0.5 h-4 w-4 text-primary focus:ring-primary"
            />
            <div>
              <span className="text-sm font-medium text-gray-700">Standard</span>
              <p className="text-xs text-gray-400 mt-0.5">Empfohlen, gute Bildqualität</p>
            </div>
          </label>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="radio"
              name="dpi"
              value={300}
              checked={dpi === 300}
              onChange={() => onDpiChange(300)}
              className="mt-0.5 h-4 w-4 text-primary focus:ring-primary"
            />
            <div>
              <span className="text-sm font-medium text-gray-700">Maximale Qualität</span>
              <p className="text-xs text-gray-400 mt-0.5">Höchste Bildschärfe, ca. 4–5× längere Bearbeitungszeit</p>
            </div>
          </label>
        </div>
      </div>

      <div className="mb-4 rounded-lg bg-gray-50 px-4 py-3">
        <p className="text-sm text-gray-700">
          <span className="font-medium">{slides.length}</span> Folien · ca.{" "}
          <span className="font-medium">{totalWords}</span> Wörter ·{" "}
          <span className={`font-medium ${scriptOverLimit ? "text-red-600" : ""}`}>{totalChars.toLocaleString("de-DE")}</span> /{" "}
          {maxChars.toLocaleString("de-DE")} Zeichen
        </p>
      </div>

      {scriptOverLimit && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 flex items-start gap-3">
          <span className="text-red-500 mt-0.5">⚠</span>
          <div className="flex-1">
            <p className="text-sm font-medium text-red-700">Skript zu lang</p>
            <p className="text-sm text-red-600 mt-0.5">
              Das Skript hat {totalChars.toLocaleString("de-DE")} Zeichen (max. {maxChars.toLocaleString("de-DE")}). Bitte kürzen Sie die Folien-Texte.
            </p>
            <button
              onClick={onBackToScripts}
              className="mt-2 px-3 py-1.5 text-sm font-medium text-red-700 border border-red-300 rounded-md hover:bg-red-100 transition-colors"
            >
              Zurück zum Skript bearbeiten
            </button>
          </div>
        </div>
      )}

      {ttsSettingsError && (
        <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mb-3">{ttsSettingsError}</p>
      )}
      <div className="flex gap-3">
        <button
          onClick={onBackToScripts}
          className="px-4 py-3 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-100 transition-colors"
        >
          Zurück
        </button>
        <button
          onClick={onStartRender}
          disabled={scriptOverLimit}
          className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Screencast erstellen
        </button>
      </div>
    </section>
  );
}
