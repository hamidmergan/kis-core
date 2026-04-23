"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import UploadZone from "../_components/UploadZone";
import { validateImageFile } from "../_utils";


export default function EditTab() {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [spinnerLabel, setSpinnerLabel] = useState("Wird bearbeitet…");
  const [error, setError] = useState("");
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultFilename, setResultFilename] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFileSelect = useCallback((f: File) => {
    const err = validateImageFile(f);
    if (err) { setError(err); return; }
    setError("");
    setFile(f);
    setResultUrl(null);
    setResultFilename(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!file || !prompt.trim()) return;
    setLoading(true);
    setSpinnerLabel("Wird bearbeitet…");
    setError("");
    setResultUrl(null);
    setResultFilename(null);
    try {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("prompt", prompt);
      const response = await backendApi.fetch("/image/edit", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setSpinnerLabel("Läuft noch – Bildbearbeitung kann etwas länger dauern…"),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const { blob, filename } = await downloadJobAsBlob(data.job_uuid);
      setResultUrl(URL.createObjectURL(blob));
      setResultFilename(filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }, [file, prompt]);

  const handleDownload = () => {
    if (!resultUrl || !resultFilename) return;
    const a = document.createElement("a");
    a.href = resultUrl;
    a.download = resultFilename;
    a.click();
  };

  return (
    <section>
      <UploadZone
        file={file}
        dragOver={dragOver}
        disabled={loading}
        inputRef={fileRef}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) handleFileSelect(f);
        }}
        onChange={handleFileSelect}
      />

      {previewUrl && (
        <div className="mb-4 rounded-lg overflow-hidden border border-gray-200">
          <img src={previewUrl} alt="Vorschau" className="w-full max-h-64 object-contain bg-gray-50" />
        </div>
      )}

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={3}
        placeholder="Beschreiben Sie die gewünschte Änderung."
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none mb-4"
      />

      {!resultUrl && (
        <button
          onClick={handleSubmit}
          disabled={!file || !prompt.trim() || loading}
          className="w-full px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Wird verarbeitet…" : "Bild bearbeiten"}
        </button>
      )}

      {loading && <Spinner label={spinnerLabel} className="justify-center mt-6" />}
      {error && <p className="mt-4 text-sm text-red-600" role="alert">{error}</p>}
      {resultUrl && (
        <div className="mt-6">
          <img src={resultUrl} alt="Bearbeitetes Bild" className="w-full rounded-lg border border-gray-200 bg-gray-50" />
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleDownload}
              className="px-5 py-2 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors flex items-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Bild
            </button>
            <button
              onClick={() => { setResultUrl(null); setResultFilename(null); }}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            >
              Neu bearbeiten
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
