"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import TtsFileUpload from "@/components/TtsFileUpload";
import TtsStatus from "@/components/TtsStatus";
import { api, pollJob, downloadJobAsBlob } from "@/lib/api";
import type { TTSState } from "@/types";

interface Voice {
  voice_id: string;
  label: string;
}

const PAUSE_OPTIONS = [
  { value: "short", label: "Kurze Pausen" },
  { value: "medium", label: "Mittlere Pausen" },
  { value: "long", label: "Lange Pausen" },
  { value: "very_long", label: "Sehr lange Pausen" },
];

export default function TtsPage() {
  const [ttsState, setTtsState] = useState<TTSState>("idle");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [ttsSelectedFile, setTtsSelectedFile] = useState<string>("");
  const [ttsDownloadBlob, setTtsDownloadBlob] = useState<Blob | null>(null);
  const [ttsDownloadName, setTtsDownloadName] = useState<string>("");
  const [ttsErrorMessage, setTtsErrorMessage] = useState<string>("");
  const [ttsProgressLabel, setTtsProgressLabel] = useState<string>("");

  // Voice selection
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");

  // Audio settings
  const [speed, setSpeed] = useState(0.9);
  const [pausePreset, setPausePreset] = useState("medium");

  useEffect(() => {
    api.getJson<{ voices: Voice[] }>("/api/voices").then((data) => {
      setVoices(data.voices);
      if (data.voices.length > 0) setVoiceId(data.voices[0].voice_id);
    }).catch(() => {});
  }, []);

  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); setTtsState("idle"); };
  }, []);

  const isProcessing = ttsState === "uploading" || ttsState === "processing";

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

    // Check job limit + storage limit before submitting
    try {
      const res = await fetch("/api/jobs/check/tts", { credentials: "include" });
      const data = await res.json();
      if (data.has_active_job) {
        setTtsErrorMessage("Sie haben bereits einen laufenden TTS-Job. Bitte warten Sie, bis er fertig ist.");
        return;
      }
      if (data.at_storage_limit) {
        const ok = window.confirm(
          `Wenn Sie fortfahren, wird "${data.evict_filename || "Ihre älteste TTS-Datei"}" gelöscht. Fortfahren?`
        );
        if (!ok) return;
      }
    } catch { /* ignore, backend handles it */ }

    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;
    setTtsState("uploading");
    setTtsProgressLabel("Wird hochgeladen…");
    try {
      // Upload file → get job_uuid
      const formData = new FormData();
      formData.append("file", pendingFile);
      formData.append("voice_id", voiceId);
      formData.append("speed", String(speed));
      formData.append("pause_preset", pausePreset);

      const uploadRes = await fetch("/api/tts", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
        throw new Error(err.detail || `Fehler: ${uploadRes.status}`);
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      setTtsState("processing");
      setTtsProgressLabel("In der Warteschlange…");

      // Poll until done
      const jobResult = await pollJob(
        job_uuid,
        (status) => {
          const step = (status.progress as { step?: string } | null)?.step;
          if (step === "extract") setTtsProgressLabel("Text wird extrahiert…");
          else if (step === "synthesize") setTtsProgressLabel("Audio wird generiert…");
          else setTtsProgressLabel("In der Warteschlange…");
        },
        3000,
        signal,
      );

      // Download result
      setTtsProgressLabel("Wird heruntergeladen…");
      const { blob, filename } = await downloadJobAsBlob(
        jobResult.job_uuid,
        `${pendingFile.name.replace(/\.[^.]+$/, "")}_EN.mp3`,
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
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Text-to-Speech</h1>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie ein Dokument hoch und lassen Sie den Inhalt auf Englisch als MP3-Audiodatei vorlesen.
          </p>

          <TtsFileUpload
            onFileSelected={handleTtsFileSelected}
            disabled={isProcessing}
          />
          {ttsSelectedFile && (
            <p className="mt-2 text-sm font-medium text-gray-700">{ttsSelectedFile}</p>
          )}

          {/* Stimme – Dropdown */}
          {voices.length > 1 && (
            <div className="mt-6 mb-6">
              <label htmlFor="voice-select" className="block text-sm font-medium text-gray-700 mb-2">
                Stimme
              </label>
              <select
                id="voice-select"
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                disabled={isProcessing}
                className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {voices.map((v) => (
                  <option key={v.voice_id} value={v.voice_id}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Geschwindigkeit – Slider */}
          <div className="mb-6">
            <label
              htmlFor="speed-slider"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
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
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#0066cc] disabled:opacity-50"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>Langsam (0.7x)</span>
              <span>Schnell (1.2x)</span>
            </div>
          </div>

          {/* Pausen – Dropdown */}
          <div className="mb-6">
            <label htmlFor="pause-select" className="block text-sm font-medium text-gray-700 mb-2">
              Pausen
            </label>
            <select
              id="pause-select"
              value={pausePreset}
              onChange={(e) => setPausePreset(e.target.value)}
              disabled={isProcessing}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {PAUSE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-6 flex items-center gap-3">
            <button
              onClick={handleSubmit}
              disabled={!pendingFile || isProcessing}
              className="self-start px-5 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isProcessing && (
                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
              )}
              {isProcessing ? (ttsProgressLabel || "MP3 wird erstellt…") : "MP3 erstellen"}
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
