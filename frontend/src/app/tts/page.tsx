"use client";

import { useCallback, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import TtsFileUpload from "@/components/TtsFileUpload";
import TtsStatus from "@/components/TtsStatus";
import { api } from "@/lib/api";
import type { TTSState } from "@/types";

const SPEED_OPTIONS = [
  { value: 0.5, label: "Sehr langsam (0.5x)" },
  { value: 0.6, label: "Langsam (0.6x)" },
  { value: 0.7, label: "Gemächlich (0.7x)" },
  { value: 0.8, label: "Gemäßigt (0.8x)" },
  { value: 0.9, label: "Leicht reduziert (0.9x)" },
  { value: 1.0, label: "Normal (1.0x)" },
  { value: 1.1, label: "Etwas schneller (1.1x)" },
  { value: 1.2, label: "Schnell (1.2x)" },
];

const PAUSE_OPTIONS = [
  { value: "short", label: "Kurze Pausen" },
  { value: "medium", label: "Mittlere Pausen" },
  { value: "long", label: "Lange Pausen" },
  { value: "very_long", label: "Sehr lange Pausen" },
];

export default function TtsPage() {
  const [ttsState, setTtsState] = useState<TTSState>("idle");
  const [ttsSelectedFile, setTtsSelectedFile] = useState<string>("");
  const [ttsDownloadBlob, setTtsDownloadBlob] = useState<Blob | null>(null);
  const [ttsDownloadName, setTtsDownloadName] = useState<string>("");
  const [ttsErrorMessage, setTtsErrorMessage] = useState<string>("");

  // Audio settings with optimized defaults
  const [speed, setSpeed] = useState(0.9);
  const [pausePreset, setPausePreset] = useState("medium");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [stability, setStability] = useState(0.70);
  const [similarityBoost, setSimilarityBoost] = useState(0.60);
  const [style, setStyle] = useState(0.20);
  const [useSpeakerBoost, setUseSpeakerBoost] = useState(true);

  const isProcessing = ttsState === "uploading" || ttsState === "processing";

  const handleTtsFileSelected = useCallback(
    async (file: File) => {
      setTtsDownloadBlob(null);
      setTtsDownloadName("");
      setTtsErrorMessage("");
      setTtsSelectedFile(file.name);
      setTtsState("uploading");

      try {
        setTtsState("processing");
        const { blob, filename } = await api.uploadFileWithFields(
          "/api/tts",
          file,
          {
            speed: String(speed),
            stability: String(stability),
            similarity_boost: String(similarityBoost),
            style: String(style),
            use_speaker_boost: String(useSpeakerBoost),
            pause_preset: pausePreset,
          },
        );

        setTtsDownloadBlob(blob);
        setTtsDownloadName(filename);
        setTtsState("done");
      } catch (err) {
        setTtsErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
        setTtsState("error");
      }
    },
    [speed, stability, similarityBoost, style, useSpeakerBoost, pausePreset],
  );

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
    setTtsSelectedFile("");
    setTtsDownloadBlob(null);
    setTtsDownloadName("");
    setTtsErrorMessage("");
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

          {/* Geschwindigkeit – Dropdown */}
          <div className="mb-4">
            <label htmlFor="speed-select" className="block text-sm font-medium text-gray-700 mb-2">
              Geschwindigkeit
            </label>
            <select
              id="speed-select"
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              disabled={isProcessing}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {SPEED_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
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

          {/* Erweiterte Optionen */}
          <div className="mb-6">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              <svg
                className={`h-4 w-4 transition-transform ${showAdvanced ? "rotate-90" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              Erweiterte Optionen
            </button>

            {showAdvanced && (
              <div className="mt-4 space-y-5 rounded-lg border border-gray-200 bg-gray-50 p-4">
                {/* Stability */}
                <div>
                  <label htmlFor="stability-slider" className="block text-sm font-medium text-gray-700 mb-1">
                    Stabilität: <span className="text-[#0066cc]">{stability.toFixed(2)}</span>
                  </label>
                  <p className="text-xs text-gray-400 mb-2">
                    Niedrig = emotionaler &amp; lebendiger. Hoch = stabiler &amp; sachlicher.
                  </p>
                  <input
                    id="stability-slider"
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={stability}
                    onChange={(e) => setStability(parseFloat(e.target.value))}
                    disabled={isProcessing}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#0066cc] disabled:opacity-50"
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>Emotional</span>
                    <span>Sachlich</span>
                  </div>
                </div>

                {/* Similarity Boost */}
                <div>
                  <label htmlFor="similarity-slider" className="block text-sm font-medium text-gray-700 mb-1">
                    Klarheit: <span className="text-[#0066cc]">{similarityBoost.toFixed(2)}</span>
                  </label>
                  <p className="text-xs text-gray-400 mb-2">
                    Wie nah an der Originalstimme. Hoch = klarer, aber evtl. Artefakte.
                  </p>
                  <input
                    id="similarity-slider"
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={similarityBoost}
                    onChange={(e) => setSimilarityBoost(parseFloat(e.target.value))}
                    disabled={isProcessing}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#0066cc] disabled:opacity-50"
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>Variabel</span>
                    <span>Original</span>
                  </div>
                </div>

                {/* Style */}
                <div>
                  <label htmlFor="style-slider" className="block text-sm font-medium text-gray-700 mb-1">
                    Stil-Intensität: <span className="text-[#0066cc]">{style.toFixed(2)}</span>
                  </label>
                  <p className="text-xs text-gray-400 mb-2">
                    Verstärkt den Stil der Stimme. Höher = ausdrucksstärker, aber mehr Latenz.
                  </p>
                  <input
                    id="style-slider"
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={style}
                    onChange={(e) => setStyle(parseFloat(e.target.value))}
                    disabled={isProcessing}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#0066cc] disabled:opacity-50"
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>Neutral</span>
                    <span>Ausdrucksstark</span>
                  </div>
                </div>

                {/* Speaker Boost */}
                <div className="flex items-center gap-3">
                  <input
                    id="speaker-boost"
                    type="checkbox"
                    checked={useSpeakerBoost}
                    onChange={(e) => setUseSpeakerBoost(e.target.checked)}
                    disabled={isProcessing}
                    className="h-4 w-4 rounded border-gray-300 text-[#0066cc] focus:ring-[#0066cc] disabled:opacity-50"
                  />
                  <div>
                    <label htmlFor="speaker-boost" className="block text-sm font-medium text-gray-700">
                      Speaker Boost
                    </label>
                    <p className="text-xs text-gray-400">
                      Verbessert die Stimmähnlichkeit (etwas mehr Latenz).
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <TtsFileUpload
            onFileSelected={handleTtsFileSelected}
            disabled={isProcessing}
          />

          {ttsSelectedFile && ttsState !== "idle" && (
            <p className="mt-3 text-xs text-gray-500">Datei: {ttsSelectedFile}</p>
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
