"use client";

import { useCallback, useRef, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";

const ACCEPTED_EXTENSIONS = [".srt", ".vtt", ".txt", ".md", ".pptx", ".docx"];
const MAX_SIZE_MB = MAX_UPLOAD_MB;
const MAX_SIZE_BYTES = MAX_UPLOAD_BYTES;

export default function ZusammenfassungPage() {
  const [processing, setProcessing] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);

  const outputFormat = "txt";
  const [errorMessage, setErrorMessage] = useState("");
  const [stallMessage, setStallMessage] = useState("");

  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return `Nur ${ACCEPTED_EXTENSIONS.join(", ")} erlaubt`;
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `Datei zu groß (max ${MAX_SIZE_MB} MB)`;
    }
    return null;
  };

  const handleFile = useCallback((file: File) => {
    setUploadError(null);
    const err = validateFile(file);
    if (err) { setUploadError(err); return; }
    setSelectedFile(file);
    setDoneJobUuid(null);
    setErrorMessage("");
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (processing) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [processing, handleFile],
  );

  const handleSubmit = async () => {
    if (!selectedFile || processing) return;
    setProcessing(true);
    setErrorMessage("");
    setStallMessage("");
    setDoneJobUuid(null);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("output_format", outputFormat);
      const response = await backendApi.fetch("/summary", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setStallMessage("Läuft noch – umfangreiche Inhalte können einige Minuten dauern…"),
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
    setSelectedFile(null);
    setDoneJobUuid(null);
    setErrorMessage("");
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Summarize</h1>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie eine Datei hoch, um deren Inhalt automatisch zusammenzufassen. Unterstützt werden
             Untertitel (srt, vtt) sowie Dokumente (txt, md, pptx, docx).
          </p>

          {/* File upload */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Datei zur Zusammenfassung auswählen"
            onClick={() => !processing && inputRef.current?.click()}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !processing) {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); if (!processing) setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            className={[
              "border-2 border-dashed rounded-lg p-10 text-center transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc]",
              dragActive ? "border-[#0066cc] bg-blue-50" : selectedFile ? "border-green-400 bg-green-50" : "border-gray-300 hover:border-gray-400",
              processing ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
            ].join(" ")}
          >
            {selectedFile ? (
              <>
                <svg className="mx-auto h-8 w-8 text-green-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <p className="text-sm font-medium text-gray-800">{selectedFile.name}</p>
                <p className="text-xs text-gray-400 mt-1">Klicken um zu ersetzen</p>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-gray-500">
                  Datei hierher ziehen oder{" "}
                  <span className="text-[#0066cc] underline">durchsuchen</span>
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {ACCEPTED_EXTENSIONS.join(", ")}
                </p>
              </>
            )}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); if (inputRef.current) inputRef.current.value = ""; }}
            className="hidden"
            aria-hidden="true"
          />
          {uploadError && (
            <p className="mt-2 text-sm text-red-600" role="alert">{uploadError}</p>
          )}

          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={handleSubmit}
              disabled={!selectedFile || processing}
              className="self-start px-5 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {processing && (
                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
              )}
              {processing ? "Wird verarbeitet…" : "Zusammenfassung erstellen"}
            </button>
          </div>

          {stallMessage && !errorMessage && (
            <p className="mt-3 text-sm text-amber-600" role="status">{stallMessage}</p>
          )}

          {errorMessage && (
            <p className="mt-3 text-sm text-red-600" role="alert">{errorMessage}</p>
          )}

          {doneJobUuid && (
            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={handleDownload}
                className="px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 transition-colors flex items-center gap-2"
              >
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Zusammenfassung
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
