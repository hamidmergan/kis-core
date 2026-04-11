"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import TtsFileUpload from "@/components/TtsFileUpload";
import TtsStatus from "@/components/TtsStatus";
import { api, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import type { TTSState } from "@/types";
import BackLink from "@/components/BackLink";

interface Voice {
  voice_id: string;
  label: string;
  description?: string | null;
  use_case?: string | null;
}

const DESCRIPTION_DE: Record<string, string> = {
  "Laid-Back": "Entspannt",
  "Casual": "Locker",
  "Formal": "Förmlich",
  "Friendly": "Freundlich",
  "Warm": "Warm",
  "Authoritative": "Autoritär",
  "Confident": "Selbstsicher",
  "Calm": "Ruhig",
  "Energetic": "Energetisch",
  "Upbeat": "Lebhaft",
  "Serious": "Sachlich",
  "Raspy": "Rau",
  "Smooth": "Weich",
  "Deep": "Tief",
  "Resonant": "Resonant",
  "Crisp": "Klar",
  "Soft": "Sanft",
  "Husky": "Heiser",
  "Clear": "Deutlich",
  "Conversational": "Gesprächig",
  "Narrative": "Erzählend",
  "Expressive": "Ausdrucksstark",
  "Melodic": "Melodisch",
  "Mature": "Reif",
  "Powerful": "Kraftvoll",
  "Bright": "Hell",
  "Grounded": "Geerdet",
  "Soothing": "Beruhigend",
  "Professional": "Professionell",
};

function translateDesc(description?: string | null): string | null {
  if (!description) return null;
  return description.split(",").map(d => {
    const key = d.trim();
    return DESCRIPTION_DE[key] ?? key;
  }).join(" · ");
}

const PAUSE_OPTIONS = [
  { value: "short", label: "Kurze Pausen" },
  { value: "medium", label: "Mittlere Pausen" },
  { value: "long", label: "Lange Pausen" },
  { value: "very_long", label: "Sehr lange Pausen" },
];

const KOKORO_ACCENT_LABEL: Record<string, string> = {
  "American": "🇺🇸",
  "British": "🇬🇧",
  "Deutsch": "🇩🇪",
};

export default function TtsPage() {
  const [ttsState, setTtsState] = useState<TTSState>("idle");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [ttsSelectedFile, setTtsSelectedFile] = useState<string>("");
  const [ttsDownloadBlob, setTtsDownloadBlob] = useState<Blob | null>(null);
  const [ttsDownloadName, setTtsDownloadName] = useState<string>("");
  const [ttsErrorMessage, setTtsErrorMessage] = useState<string>("");
  const [ttsProgressLabel, setTtsProgressLabel] = useState<string>("");

  // Provider
  const [provider, setProvider] = useState<"elevenlabs" | "kokoro" | "mylab" | "thorsten">("elevenlabs");
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState(false);
  const [kokoroEnabled, setKokoroEnabled] = useState(false);
  const [mylabEnabled, setMylabEnabled] = useState(false);
  const [thorstenEnabled, setThorstenEnabled] = useState(false);
  const [providersLoaded, setProvidersLoaded] = useState(false);

  // Voice selection
  const [voices, setVoices] = useState<Voice[]>([]);
  const [kokoroVoices, setKokoroVoices] = useState<Array<{voice_id: string; name: string; language?: string; accent: string; gender: string}>>([]);
  const [mylabVoices, setMylabVoices] = useState<Array<{voice_id: string; name: string; description: string}>>([]);
  const [voiceId, setVoiceId] = useState("");

  // Audio settings
  const [speed, setSpeed] = useState(1.0);
  const [pausePreset, setPausePreset] = useState("medium");

  useEffect(() => {
    api.getJson<{ elevenlabs_enabled: boolean; fish_speech_enabled: boolean; kokoro_enabled: boolean; mylab_enabled: boolean; thorsten_enabled: boolean }>("/api/tts/providers").then((data) => {
      setElevenlabsEnabled(data.elevenlabs_enabled);
      setKokoroEnabled(data.kokoro_enabled ?? false);
      setMylabEnabled(data.mylab_enabled ?? false);
      setThorstenEnabled(data.thorsten_enabled ?? false);
      if (!data.elevenlabs_enabled && data.kokoro_enabled) setProvider("kokoro");
      else if (!data.elevenlabs_enabled && !data.kokoro_enabled && data.mylab_enabled) setProvider("mylab");
      else if (!data.elevenlabs_enabled && !data.kokoro_enabled && !data.mylab_enabled && data.thorsten_enabled) setProvider("thorsten");
      if (data.elevenlabs_enabled) {
        api.getJson<{ voices: Voice[] }>("/api/voices").then((vData) => {
          setVoices(vData.voices);
          if (vData.voices.length > 0) setVoiceId(vData.voices[0].voice_id);
        }).catch(() => {});
      }
      if (data.kokoro_enabled) {
        api.getJson<{ voices: Array<{voice_id: string; name: string; accent: string; gender: string}> }>("/api/kokoro/voices")
          .then((d) => {
            setKokoroVoices(d.voices);
          }).catch(() => {});
      }
      if (data.mylab_enabled) {
        api.getJson<{ voices: Array<{voice_id: string; name: string; description: string}> }>("/api/mylab/voices")
          .then((d) => {
            setMylabVoices(d.voices);
          }).catch(() => {});
      }
    }).catch(() => {
      setElevenlabsEnabled(true);
    }).finally(() => {
      setProvidersLoaded(true);
    });
  }, []);

  // Wenn Provider wechselt → passende Stimme vorauswählen
  useEffect(() => {
    if (provider === "kokoro") {
      if (kokoroVoices.length > 0) setVoiceId(kokoroVoices[0].voice_id);
    } else if (provider === "mylab") {
      if (mylabVoices.length > 0) setVoiceId(mylabVoices[0].voice_id);
    } else if (provider === "thorsten") {
      setVoiceId("thorsten");
    } else {
      if (voices.length > 0) setVoiceId(voices[0].voice_id);
    }
  }, [provider, voices, kokoroVoices, mylabVoices, thorstenEnabled]);

  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); setTtsState("idle"); };
  }, []);

  const isProcessing = ttsState === "uploading" || ttsState === "processing";
  const noProvider = providersLoaded && !elevenlabsEnabled && !kokoroEnabled && !mylabEnabled && !thorstenEnabled;

  const handleTtsFileSelected = useCallback((file: File) => {
    setPendingFile(file);
    setTtsSelectedFile(file.name);
    setTtsDownloadBlob(null);
    setTtsDownloadName("");
    setTtsErrorMessage("");
    setTtsState("idle");
  }, []);

  const handleSubmit = async () => {
    if (!pendingFile || isProcessing) return;

    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;
    setTtsState("uploading");
    setTtsProgressLabel("Wird hochgeladen…");
    try {
      const voiceLabel = provider === "kokoro"
        ? (() => { const v = kokoroVoices.find(x => x.voice_id === voiceId); return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId; })()
        : provider === "mylab"
        ? (mylabVoices.find(x => x.voice_id === voiceId)?.name ?? voiceId)
        : provider === "thorsten"
        ? "Thorsten"
        : (voices.find(x => x.voice_id === voiceId)?.label ?? voiceId);

      const formData = new FormData();
      formData.append("file", pendingFile);
      formData.append("voice_id", voiceId);
      formData.append("voice_label", voiceLabel);
      formData.append("speed", String(speed));
      formData.append("pause_preset", pausePreset);
      formData.append("provider", provider);

      const uploadRes = await fetch("/api/tts", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      setTtsState("processing");
      setTtsProgressLabel("In der Warteschlange…");

      const jobResult = await pollJob(
        job_uuid,
        (status) => {
          const p = status.progress as { step?: string; chunk?: number; total?: number } | null;
          if (p?.step === "extract") setTtsProgressLabel("Text wird extrahiert…");
          else if (p?.step === "synthesize" && p.chunk && p.total)
            setTtsProgressLabel(`Chunk ${p.chunk} von ${p.total} wird synthetisiert…`);
          else if (p?.step === "synthesize") setTtsProgressLabel("Audio wird generiert…");
          else setTtsProgressLabel("In der Warteschlange…");
        },
        3000,
        signal,
        () => setTtsProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"),
        60_000,
      );

      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      setTtsProgressLabel("Wird heruntergeladen…");
      const { blob, filename } = await downloadJobAsBlob(
        jobResult.job_uuid,
        `${pendingFile.name.replace(/\.[^.]+$/, "")}.mp3`,
      );
      setTtsDownloadBlob(blob);
      setTtsDownloadName(filename);
      currentJobUuidRef.current = null;
      setTtsState("done");
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      currentJobUuidRef.current = null;
      setTtsErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
      setTtsState("error");
    }
  };

  const handleTtsDownload = () => {
    if (!ttsDownloadBlob) return;
    const url = URL.createObjectURL(ttsDownloadBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = ttsDownloadName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleTtsReset = () => {
    setTtsState("idle");
    setPendingFile(null);
    setTtsSelectedFile("");
    setTtsDownloadBlob(null);
    setTtsDownloadName("");
    setTtsErrorMessage("");
    setTtsProgressLabel("");
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <section>
          <h1 className="text-xl font-bold mb-1">Text in Sprache</h1>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie ein Dokument hoch und lassen Sie den Inhalt als MP3-Audiodatei vorlesen.
          </p>

          <TtsFileUpload
            onFileSelected={handleTtsFileSelected}
            disabled={isProcessing || noProvider}
            selectedFilename={ttsSelectedFile || undefined}
          />
          {noProvider && (
            <p className="mt-3 text-sm text-gray-400">Kein TTS-Anbieter aktiv — bitte im Admin-Bereich einen Anbieter freischalten.</p>
          )}

          {/* Provider */}
          {providersLoaded && (elevenlabsEnabled || kokoroEnabled || mylabEnabled || thorstenEnabled) && (
          <div className="mt-6 mb-2">
            <label htmlFor="provider-select" className="block text-sm font-medium text-gray-700 mb-2">
              TTS-Anbieter
            </label>
            <select
              id="provider-select"
              value={provider}
              onChange={(e) => setProvider(e.target.value as "elevenlabs" | "kokoro" | "mylab" | "thorsten")}
              disabled={isProcessing}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {elevenlabsEnabled && <option value="elevenlabs">ElevenLabs</option>}
              {kokoroEnabled && <option value="kokoro">Kokoro TTS</option>}
              {mylabEnabled && <option value="mylab">THL myLab (XTTS-v2)</option>}
              {thorstenEnabled && <option value="thorsten">Thorsten (Deutsch, lokal)</option>}
            </select>
          </div>
          )}

          {/* Stimme */}
          {providersLoaded && (elevenlabsEnabled || kokoroEnabled || mylabEnabled || thorstenEnabled) && (
          <div className="mt-4 mb-6 space-y-3">
            <div>
              <label htmlFor="voice-select" className="block text-sm font-medium text-gray-700 mb-2">
                Stimme
              </label>
              <select
                id="voice-select"
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                disabled={isProcessing}
                className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {provider === "kokoro" && kokoroVoices.map((v) => (
                  <option key={v.voice_id} value={v.voice_id}>
                    {KOKORO_ACCENT_LABEL[v.accent] ?? ""} {v.name}
                  </option>
                ))}
                {provider === "mylab" && mylabVoices.map((v) => (
                  <option key={v.voice_id} value={v.voice_id}>
                    {v.name} – {v.description}
                  </option>
                ))}
                {provider === "thorsten" && (
                  <option value="thorsten">Thorsten – Neutral, klar</option>
                )}
                {provider === "elevenlabs" && voices.map((v) => {
                  const desc = translateDesc(v.description);
                  return (
                    <option key={v.voice_id} value={v.voice_id}>
                      {desc ? `${v.label} – ${desc}` : v.label}
                    </option>
                  );
                })}
              </select>
            </div>
            {provider === "elevenlabs" && (
              <a
                href="/tools/tts/voices"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                Stimmen anhören →
              </a>
            )}
            {provider === "kokoro" && (
              <a
                href="/tools/tts/voices?tab=kokoro"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                Stimmen anhören →
              </a>
            )}
            {provider === "mylab" && (
              <a
                href="/tools/tts/voices?tab=mylab"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                Stimmen anhören →
              </a>
            )}
          </div>
          )}


          {/* Geschwindigkeit */}
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
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              disabled={isProcessing}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary disabled:opacity-50"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>Langsam (0.7x)</span>
              <span>Schnell (1.2x)</span>
            </div>
          </div>

          {/* Pausen (nur ElevenLabs) */}
          {provider === "elevenlabs" && (
            <div className="mb-6">
              <label htmlFor="pause-select" className="block text-sm font-medium text-gray-700 mb-2">
                Pausen
              </label>
              <select
                id="pause-select"
                value={pausePreset}
                onChange={(e) => setPausePreset(e.target.value)}
                disabled={isProcessing}
                className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {PAUSE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {ttsState !== "done" && (
            <div className="mb-6 flex items-center gap-3">
              <button
                onClick={handleSubmit}
                disabled={!pendingFile || isProcessing || noProvider}
                className="self-start px-5 py-2 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                MP3 erstellen
              </button>
              {isProcessing && (
                <button
                  onClick={() => {
                    const uuid = currentJobUuidRef.current;
                    currentJobUuidRef.current = null;
                    abortControllerRef.current?.abort();
                    if (uuid) { fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {}); window.dispatchEvent(new CustomEvent("kis-jobs-changed")); }
                    setTtsState("idle");
                  }}
                  className="px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Abbrechen
                </button>
              )}
            </div>
          )}

          <TtsStatus
            state={ttsState}
            fileName={ttsDownloadName}
            errorMessage={ttsErrorMessage}
            onDownload={handleTtsDownload}
            onReset={handleTtsReset}
          />
        </section>
      </div>
    </ProtectedRoute>
  );
}
