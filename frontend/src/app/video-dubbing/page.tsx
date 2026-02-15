"use client";

import { useCallback, useRef, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import VideoDubbingStatus from "@/components/VideoDubbingStatus";
import { backendApi } from "@/lib/api";
import type { VideoDubbingState } from "@/types";

const VIDEO_EXTENSIONS = [".mp4"];

const LANGUAGE_OPTIONS = [
  { value: "de", label: "Deutsch" },
  { value: "en", label: "Englisch" },
  { value: "fr", label: "Französisch" },
  { value: "es", label: "Spanisch" },
  { value: "it", label: "Italienisch" },
  { value: "pt", label: "Portugiesisch" },
  { value: "nl", label: "Niederländisch" },
  { value: "pl", label: "Polnisch" },
  { value: "ru", label: "Russisch" },
  { value: "zh", label: "Chinesisch" },
  { value: "ja", label: "Japanisch" },
  { value: "ko", label: "Koreanisch" },
];

export default function VideoDubbingPage() {
  const [state, setState] = useState<VideoDubbingState>("idle");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [sourceLang, setSourceLang] = useState("de");
  const [targetLang, setTargetLang] = useState("en");
  const [dropBackground, setDropBackground] = useState(false);
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [downloadName, setDownloadName] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [fileError, setFileError] = useState<string | null>(null);

  const videoRef = useRef<HTMLInputElement>(null);

  const isProcessing = state === "uploading" || state === "processing";

  const handleSubmit = useCallback(async () => {
    if (!videoFile) return;

    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
    setState("uploading");

    try {
      setState("processing");

      const { blob, filename } = await backendApi.uploadFileWithFields(
        "/video-dubbing",
        videoFile,
        {
          source_lang: sourceLang,
          target_lang: targetLang,
          drop_background_audio: String(dropBackground),
          num_speakers: "0",
        },
        "video",
      );

      setDownloadBlob(blob);
      setDownloadName(filename);
      setState("done");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
      setState("error");
    }
  }, [videoFile, sourceLang, targetLang, dropBackground]);

  const handleDownload = () => {
    if (!downloadBlob) return;
    const url = URL.createObjectURL(downloadBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleReset = () => {
    setState("idle");
    setVideoFile(null);
    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
    setFileError(null);
    if (videoRef.current) videoRef.current.value = "";
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Video-Dubbing</h1>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie ein Video hoch, um es automatisch in eine andere Sprache zu synchronisieren.
          </p>

          {/* Source language */}
          <div className="mb-4">
            <label htmlFor="source-lang" className="block text-sm font-medium text-gray-700 mb-2">
              Quellsprache
            </label>
            <select
              id="source-lang"
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              disabled={isProcessing}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Target language */}
          <div className="mb-4">
            <label htmlFor="target-lang" className="block text-sm font-medium text-gray-700 mb-2">
              Zielsprache
            </label>
            <select
              id="target-lang"
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              disabled={isProcessing}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {LANGUAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Drop background audio */}
          <div className="mb-6 flex items-center gap-3">
            <input
              id="drop-background"
              type="checkbox"
              checked={dropBackground}
              onChange={(e) => setDropBackground(e.target.checked)}
              disabled={isProcessing}
              className="h-4 w-4 rounded border-gray-300 text-[#0066cc] focus:ring-[#0066cc] disabled:opacity-50"
            />
            <div>
              <label htmlFor="drop-background" className="text-sm font-medium text-gray-700">
                Hintergrundgeräusche entfernen
              </label>
              <p className="text-xs text-gray-400">Entfernt Hintergrundmusik und Geräusche für eine klarere Synchronisation.</p>
            </div>
          </div>

          {/* Video file */}
          <div className="mb-6">
            <label htmlFor="video-input" className="block text-sm font-medium text-gray-700 mb-1">
              Video (.mp4)
            </label>
            <input
              ref={videoRef}
              id="video-input"
              type="file"
              accept={VIDEO_EXTENSIONS.join(",")}
              disabled={isProcessing}
              onChange={(e) => {
                setFileError(null);
                const file = e.target.files?.[0];
                if (!file) return;
                const ext = "." + file.name.split(".").pop()?.toLowerCase();
                if (!VIDEO_EXTENSIONS.includes(ext)) {
                  setFileError(`Nur ${VIDEO_EXTENSIONS.join(", ")} erlaubt`);
                  return;
                }
                setVideoFile(file);
              }}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-[#0066cc] file:text-white hover:file:bg-[#0055aa] disabled:opacity-50"
            />
            {fileError && (
              <p className="mt-2 text-sm text-red-600" role="alert">{fileError}</p>
            )}
          </div>

          {/* Submit button */}
          <button
            onClick={handleSubmit}
            disabled={!videoFile || isProcessing}
            className="w-full px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Dubbing starten
          </button>

          <VideoDubbingStatus
            state={state}
            fileName={downloadName}
            errorMessage={errorMessage}
            onDownload={handleDownload}
            onReset={handleReset}
          />
        </section>
      </div>
    </ProtectedRoute>
  );
}
