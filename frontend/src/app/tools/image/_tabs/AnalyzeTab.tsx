"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import UploadZone from "../_components/UploadZone";
import { validateImageFile } from "../_utils";


export default function AnalyzeTab() {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [spinnerLabel, setSpinnerLabel] = useState("Wird analysiert…");
  const [error, setError] = useState("");
  const [resultText, setResultText] = useState<string | null>(null);
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
    setResultText(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!file) return;
    setLoading(true);
    setSpinnerLabel("Wird analysiert…");
    setError("");
    setResultText(null);
    try {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("prompt", prompt);
      const response = await backendApi.fetch("/image/analyze", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setSpinnerLabel("Läuft noch – Bildanalyse kann etwas länger dauern…"),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const { blob } = await downloadJobAsBlob(data.job_uuid);
      const text = await blob.text();
      setResultText(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }, [file, prompt]);

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
        placeholder="Spezifische Frage stellen (optional) – sonst wird das Bild automatisch vollständig beschrieben."
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none mb-4"
      />

      {!resultText && (
        <button
          onClick={handleSubmit}
          disabled={!file || loading}
          className="w-full px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Wird verarbeitet…" : "Analysieren"}
        </button>
      )}

      {loading && <Spinner label={spinnerLabel} className="justify-center mt-6" />}
      {error && <p className="mt-4 text-sm text-red-600" role="alert">{error}</p>}
      {resultText && (
        <div className="mt-6">
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 mb-3">
            <p className="text-sm text-gray-800 whitespace-pre-wrap">{resultText}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                const blob = new Blob([resultText], { type: "text/plain" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = file ? file.name.replace(/\.[^.]+$/, "_analyse.txt") : "analyse.txt";
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="px-5 py-2 bg-primary text-white text-sm font-medium rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors flex items-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              TXT
            </button>
            <button
              onClick={() => setResultText(null)}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-100 transition-colors"
            >
              Neu analysieren
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
