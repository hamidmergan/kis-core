"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import TtsFileUpload from "@/components/jobs/TtsFileUpload";
import TtsStatus from "@/components/jobs/TtsStatus";
import { api, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import type { TTSState } from "@/types";
import BackLink from "@/components/ui/BackLink";
import Select from "@/components/ui/Select";

interface Voice {
  voice_id: string;
  label: string;
  description?: string | null;
  use_case?: string | null;
}

const KOKORO_ACCENT_LABEL: Record<string, string> = {
  "American": "🇺🇸",
  "British": "🇬🇧",
};

const MYLAB_LANGUAGE_FLAG: Record<string, string> = {
  "de": "🇩🇪",
  "en": "🇺🇸",
};

const PAUSE_KEYS = ["short", "medium", "long", "very_long"] as const;

export default function TtsPage() {
  const t = useTranslations("tools.tts");
  const tDesc = useTranslations("tools.tts.voiceDescription");
  const tProgress = useTranslations("tools.tts.progress");
  const tCommon = useTranslations("common");

  const translateDesc = useCallback((description?: string | null): string | null => {
    if (!description) return null;
    return description.split(",").map(d => {
      const key = d.trim();
      // tDesc.has() is not available; use try-catch via has check using raw keys.
      const known = ["Laid-Back","Casual","Formal","Friendly","Warm","Authoritative","Confident","Calm","Energetic","Upbeat","Serious","Raspy","Smooth","Deep","Resonant","Crisp","Soft","Husky","Clear","Conversational","Narrative","Expressive","Melodic","Mature","Powerful","Bright","Grounded","Soothing","Professional"];
      return known.includes(key) ? tDesc(key) : key;
    }).join(" · ");
  }, [tDesc]);

  const [ttsState, setTtsState] = useState<TTSState>("idle");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [ttsSelectedFile, setTtsSelectedFile] = useState<string>("");
  const [ttsDownloadBlob, setTtsDownloadBlob] = useState<Blob | null>(null);
  const [ttsDownloadName, setTtsDownloadName] = useState<string>("");
  const [ttsErrorMessage, setTtsErrorMessage] = useState<string>("");
  const [ttsProgressLabel, setTtsProgressLabel] = useState<string>("");

  // Provider
  const [provider, setProvider] = useState<"elevenlabs" | "kokoro" | "mylab">("elevenlabs");
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState(false);
  const [kokoroEnabled, setKokoroEnabled] = useState(false);
  const [mylabEnabled, setMylabEnabled] = useState(false);
  const [providersLoaded, setProvidersLoaded] = useState(false);

  // Voice selection
  const [voices, setVoices] = useState<Voice[]>([]);
  const [kokoroVoices, setKokoroVoices] = useState<Array<{voice_id: string; name: string; language?: string; accent: string; gender: string}>>([]);
  const [mylabVoices, setMylabVoices] = useState<Array<{voice_id: string; name: string; description: string; language?: string}>>([]);
  const [voiceId, setVoiceId] = useState("");

  // Audio settings
  const [speed, setSpeed] = useState(1.0);
  const [pausePreset, setPausePreset] = useState("medium");

  useEffect(() => {
    api.getJson<{ elevenlabs_enabled: boolean; kokoro_enabled: boolean; mylab_enabled: boolean }>("/api/tts/providers").then((data) => {
      setElevenlabsEnabled(data.elevenlabs_enabled);
      setKokoroEnabled(data.kokoro_enabled ?? false);
      setMylabEnabled(data.mylab_enabled ?? false);
      if (data.elevenlabs_enabled) setProvider("elevenlabs");
      else if (data.kokoro_enabled) setProvider("kokoro");
      else if (data.mylab_enabled) setProvider("mylab");
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
        api.getJson<{ voices: Array<{voice_id: string; name: string; description: string; language?: string}> }>("/api/mylab/voices")
          .then((d) => {
            setMylabVoices(d.voices);
          }).catch(() => {});
      }
    }).catch(() => {
      // Provider check failed — leave all disabled, noProvider message will show.
    }).finally(() => {
      setProvidersLoaded(true);
    });
  }, []);

  // When provider changes, preselect a matching voice
  useEffect(() => {
    if (provider === "kokoro") {
      if (kokoroVoices.length > 0) setVoiceId(kokoroVoices[0].voice_id);
    } else if (provider === "mylab") {
      if (mylabVoices.length > 0) setVoiceId(mylabVoices[0].voice_id);
    } else {
      if (voices.length > 0) setVoiceId(voices[0].voice_id);
    }
  }, [provider, voices, kokoroVoices, mylabVoices]);

  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); setTtsState("idle"); };
  }, []);

  const isProcessing = ttsState === "uploading" || ttsState === "processing";
  const noProvider = providersLoaded && !elevenlabsEnabled && !kokoroEnabled && !mylabEnabled;

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
    setTtsProgressLabel(tProgress("uploading"));
    try {
      const voiceLabel = provider === "kokoro"
        ? (() => { const v = kokoroVoices.find(x => x.voice_id === voiceId); return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId; })()
        : provider === "mylab"
        ? (() => { const v = mylabVoices.find(x => x.voice_id === voiceId); return v ? `${MYLAB_LANGUAGE_FLAG[v.language ?? ""] ?? ""} ${v.name}`.trim() : voiceId; })()
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
        const err = await uploadRes.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, `${tCommon("unknownError")}: ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      setTtsState("processing");
      setTtsProgressLabel(tProgress("queued"));

      const jobResult = await pollJob(
        job_uuid,
        (status) => {
          const p = status.progress as { step?: string; chunk?: number; total?: number } | null;
          if (p?.step === "extract") setTtsProgressLabel(tProgress("extracting"));
          else if (p?.step === "synthesize" && p.chunk && p.total)
            setTtsProgressLabel(tProgress("synthesizingChunk", { chunk: p.chunk, total: p.total }));
          else if (p?.step === "synthesize") setTtsProgressLabel(tProgress("synthesizing"));
          else setTtsProgressLabel(tProgress("queued"));
        },
        3000,
        signal,
        () => setTtsProgressLabel(tProgress("noProgress")),
        60_000,
      );

      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      setTtsProgressLabel(tProgress("downloading"));
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
      setTtsErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
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
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <section>
          <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
          <p className="text-sm text-muted mb-6">
            {t("intro")}
          </p>

          <TtsFileUpload
            onFileSelected={handleTtsFileSelected}
            disabled={isProcessing || noProvider}
            selectedFilename={ttsSelectedFile || undefined}
          />
          {noProvider && (
            <p className="mt-3 text-sm text-muted-soft">{t("noProvider")}</p>
          )}

          {/* Provider */}
          {providersLoaded && (elevenlabsEnabled || kokoroEnabled || mylabEnabled) && (
          <div className="mt-6 mb-2">
            <label htmlFor="provider-select" className="block text-sm font-medium text-foreground-soft mb-2">
              {t("providerLabel")}
            </label>
            <Select
              id="provider-select"
              value={provider}
              onChange={(v) => setProvider(v as "elevenlabs" | "kokoro" | "mylab")}
              disabled={isProcessing}
              options={[
                ...(elevenlabsEnabled ? [{ value: "elevenlabs", label: "ElevenLabs" }] : []),
                ...(kokoroEnabled ? [{ value: "kokoro", label: "Kokoro TTS" }] : []),
                ...(mylabEnabled ? [{ value: "mylab", label: "THL myLab (XTTS-v2)" }] : []),
              ]}
            />
          </div>
          )}

          {/* Voice */}
          {providersLoaded && (elevenlabsEnabled || kokoroEnabled || mylabEnabled) && (
          <div className="mt-4 mb-6 space-y-3">
            <div>
              <label htmlFor="voice-select" className="block text-sm font-medium text-foreground-soft mb-2">
                {t("voiceLabel")}
              </label>
              <Select
                id="voice-select"
                value={voiceId}
                onChange={setVoiceId}
                disabled={isProcessing}
                options={
                  provider === "kokoro"
                    ? kokoroVoices.map((v) => ({ value: v.voice_id, label: `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() }))
                    : provider === "mylab"
                    ? mylabVoices.map((v) => ({ value: v.voice_id, label: `${MYLAB_LANGUAGE_FLAG[v.language ?? ""] ?? ""} ${v.name} - ${v.description}`.trim() }))
                    : voices.map((v) => {
                        const desc = translateDesc(v.description);
                        return { value: v.voice_id, label: desc ? `${v.label} - ${desc}` : v.label };
                      })
                }
              />
            </div>
            {provider === "elevenlabs" && (
              <a
                href="/tools/tts/voices"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-kb hover:underline"
              >
                {t("previewVoices")}
              </a>
            )}
            {provider === "kokoro" && (
              <a
                href="/tools/tts/voices?tab=kokoro"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-kb hover:underline"
              >
                {t("previewVoices")}
              </a>
            )}
            {provider === "mylab" && (
              <a
                href="/tools/tts/voices?tab=mylab"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-kb hover:underline"
              >
                {t("previewVoices")}
              </a>
            )}
          </div>
          )}


          {/* Speed */}
          <div className="mb-6">
            <label htmlFor="speed-slider" className="block text-sm font-medium text-foreground-soft mb-2">
              {t("speed", { speed: speed.toFixed(1) })}
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
              className="w-full h-2 bg-surface-dim rounded-lg appearance-none cursor-pointer accent-kb disabled:opacity-50"
            />
            <div className="flex justify-between text-xs text-muted-soft mt-1">
              <span>{t("speedSlow")}</span>
              <span>{t("speedFast")}</span>
            </div>
          </div>

          {/* Pauses (ElevenLabs only) */}
          {provider === "elevenlabs" && (
            <div className="mb-6">
              <label htmlFor="pause-select" className="block text-sm font-medium text-foreground-soft mb-2">
                {t("pauses")}
              </label>
              <Select
                id="pause-select"
                value={pausePreset}
                onChange={setPausePreset}
                disabled={isProcessing}
                options={PAUSE_KEYS.map((k) => ({ value: k, label: t(`pause.${k}`) }))}
              />
            </div>
          )}

          {ttsState !== "done" && (
            <div className="mb-6 flex items-center gap-3">
              <button
                onClick={handleSubmit}
                disabled={!pendingFile || isProcessing || noProvider}
                className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("submit")}
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
                  className="btn-cancel px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  {t("cancel")}
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
