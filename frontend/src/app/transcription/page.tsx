"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import TranscriptionFileUpload from "@/components/TranscriptionFileUpload";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";

const FORMAT_OPTIONS = [
  { value: "text", label: "Text (.txt)" },
  { value: "srt", label: "SRT (.srt)" },
  { value: "vtt", label: "VTT (.vtt)" },
];

export default function TranscriptionPage() {
  const [processing, setProcessing] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [stallMessage, setStallMessage] = useState<string>("");
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);

  const [responseFormat, setResponseFormat] = useState("text");
  const [diarize, setDiarize] = useState(false);
  const [diarizeEnabled, setDiarizeEnabled] = useState(false);

  useEffect(() => {
    fetch("/api/admin/features", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setDiarizeEnabled(d.diarize_enabled ?? false))
      .catch(() => {});
  }, []);

  const handleFileSelected = useCallback((file: File) => {
    setPendingFile(file);
    setSelectedFile(file.name);
    setErrorMessage("");
    setDoneJobUuid(null);
  }, []);

  const handleSubmit = async () => {
    if (!pendingFile || processing) return;
    setProcessing(true);
    setErrorMessage("");
    setStallMessage("");
    setDoneJobUuid(null);
    try {
      const formData = new FormData();
      formData.append("file", pendingFile);
      formData.append("task", "transcribe");
      formData.append("response_format", responseFormat);
      if (diarize) formData.append("diarize", "true");
      const response = await backendApi.fetch("/transcription", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setStallMessage("Läuft noch – lange Audiodateien können einige Minuten dauern…"),
        60_000,
      );
      setDoneJobUuid(data.job_uuid);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!doneJobUuid) return;
    try {
      const { blob, filename } = await downloadJobAsBlob(doneJobUuid);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Download fehlgeschlagen");
    }
  };

  const handleReset = () => {
    setPendingFile(null);
    setSelectedFile("");
    setErrorMessage("");
    setDoneJobUuid(null);
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Transkription</h1>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie eine Audio- oder Videodatei hoch, um sie in der Originalsprache zu transkribieren.
          </p>

          <TranscriptionFileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />

          <div className="mb-6">
            <span className="block text-sm font-medium text-gray-700 mb-2">Ausgabeformat</span>
            <div className="flex gap-6">
              {FORMAT_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="response-format"
                    value={opt.value}
                    checked={responseFormat === opt.value}
                    onChange={() => setResponseFormat(opt.value)}
                    disabled={processing}
                    className="accent-[#0066cc]"
                  />
                  <span className="text-sm text-gray-700">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {diarizeEnabled && (
            <div className="mb-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={diarize}
                  onChange={(e) => setDiarize(e.target.checked)}
                  disabled={processing}
                  className="accent-[#0066cc]"
                />
                <span className="text-sm text-gray-700">Sprecher erkennen (Diarisierung)</span>
              </label>
              <p className="text-xs text-gray-400 mt-1 ml-5">Experimentell – funktioniert am besten bei 2–5 Sprechern</p>
            </div>
          )}

          <div className="mb-6">
            <button
              onClick={handleSubmit}
              disabled={!pendingFile || processing}
              className="self-start px-5 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {processing && (
                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
              )}
              {processing ? "Wird verarbeitet…" : "Transkription starten"}
            </button>
          </div>

          {stallMessage && !errorMessage && (
            <p className="text-sm text-amber-600" role="status">{stallMessage}</p>
          )}

          {errorMessage && (
            <p className="text-sm text-red-600" role="alert">{errorMessage}</p>
          )}

          {doneJobUuid && (
            <div className="mt-2 flex items-center gap-3">
              <button
                onClick={handleDownload}
                className="px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 transition-colors flex items-center gap-2"
              >
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Transkription
              </button>
              <button
                onClick={handleReset}
                className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 transition-colors"
              >
                Neue Datei
              </button>
            </div>
          )}
        </section>
      </div>
    </ProtectedRoute>
  );
}
