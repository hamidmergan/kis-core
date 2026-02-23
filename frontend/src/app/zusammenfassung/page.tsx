"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import PromptChips from "@/components/PromptChips";
import { backendApi } from "@/lib/api";
import type { SummaryState } from "@/types";

const ACCEPTED_EXTENSIONS = [".mp3", ".srt", ".vtt", ".txt", ".md", ".pptx", ".docx"];
const MAX_SIZE_MB = 500;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

const FORMAT_OPTIONS = [
  { value: "txt", label: "Nur Text (.txt)" },
  { value: "md", label: "Markdown (.md)" },
];

export default function ZusammenfassungPage() {
  const [state, setState] = useState<SummaryState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const [userPrompt, setUserPrompt] = useState("");
  const [outputFormat, setOutputFormat] = useState("md");

  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [downloadName, setDownloadName] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); setState("idle"); };
  }, []);

  const isProcessing = state === "processing";

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
    setState("idle");
    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (isProcessing) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [isProcessing, handleFile],
  );

  const appendChip = (chip: string) => {
    setUserPrompt((prev) =>
      prev.trim() ? `${prev.trimEnd()}\n- ${chip}` : `- ${chip}`,
    );
  };

  const handleSubmit = async () => {
    if (!selectedFile || isProcessing) return;
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;
    setState("processing");
    setErrorMessage("");
    setDownloadBlob(null);
    setDownloadName("");
    try {
      const { blob, filename } = await backendApi.uploadFileWithFields(
        "/summary",
        selectedFile,
        { user_prompt: userPrompt, output_format: outputFormat },
        "file",
        signal,
      );
      setDownloadBlob(blob);
      setDownloadName(filename);
      setState("done");
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
      setState("error");
    }
  };

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
    setSelectedFile(null);
    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
    setUserPrompt("");
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Zusammenfassung</h1>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie eine Datei hoch, um deren Inhalt automatisch zusammenzufassen. Unterstützt werden
            Audio (mp3), Untertitel (srt, vtt) sowie Dokumente (txt, md, pptx, docx).
          </p>

          {/* File upload */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Datei zur Zusammenfassung auswählen"
            onClick={() => !isProcessing && inputRef.current?.click()}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !isProcessing) {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); if (!isProcessing) setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            className={[
              "border-2 border-dashed rounded-lg p-10 text-center transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc]",
              dragActive ? "border-[#0066cc] bg-blue-50" : "border-gray-300 hover:border-gray-400",
              isProcessing ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
            ].join(" ")}
          >
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-3"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            {selectedFile ? (
              <p className="text-sm font-medium text-gray-700">
                {selectedFile.name}{" "}
                <span className="text-gray-400 text-xs">
                  ({(selectedFile.size / 1024 / 1024).toFixed(1)} MB)
                </span>
              </p>
            ) : (
              <>
                <p className="text-sm font-medium text-gray-500">
                  Datei hierher ziehen oder{" "}
                  <span className="text-[#0066cc] underline">durchsuchen</span>
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {ACCEPTED_EXTENSIONS.join(", ")} (max {MAX_SIZE_MB} MB)
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

          {/* User prompt + chips */}
          <div className="mt-6">
            <label htmlFor="user-prompt" className="block text-sm font-medium text-gray-700 mb-2">
              Zusätzliche Anweisungen{" "}
              <span className="font-normal text-gray-400">(optional)</span>
            </label>
            <textarea
              id="user-prompt"
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              disabled={isProcessing}
              rows={3}
              placeholder="z. B. Auf Deutsch, maximal 5 Sätze …"
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm placeholder:text-gray-400 focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed resize-y"
            />
            <PromptChips onChipClick={appendChip} disabled={isProcessing} />
          </div>

          {/* Output format */}
          <div className="mt-6">
            <span className="block text-sm font-medium text-gray-700 mb-2">Ausgabeformat</span>
            <div className="flex gap-6">
              {FORMAT_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="output-format"
                    value={opt.value}
                    checked={outputFormat === opt.value}
                    onChange={() => setOutputFormat(opt.value)}
                    disabled={isProcessing}
                    className="accent-[#0066cc]"
                  />
                  <span className="text-sm text-gray-700">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Submit + result */}
          <div className="mt-6 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <button
                onClick={handleSubmit}
                disabled={!selectedFile || isProcessing}
                className="self-start px-5 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isProcessing && (
                  <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
                )}
                {isProcessing ? "Zusammenfassung wird erstellt…" : "Zusammenfassung erstellen"}
              </button>
              {isProcessing && (
                <button
                  onClick={() => { abortControllerRef.current?.abort(); setState("idle"); }}
                  className="px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Abbrechen
                </button>
              )}
            </div>

            {state === "done" && (
              <div className="rounded-lg border border-gray-200 bg-white p-6" role="status" aria-live="polite">
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <svg className="h-5 w-5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-sm font-medium text-gray-900">Fertig! Download bereit</span>
                  </div>
                  {downloadName && <p className="text-xs text-gray-500">{downloadName}</p>}
                  <div className="flex gap-3">
                    <button
                      onClick={handleDownload}
                      className="px-4 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
                    >
                      Herunterladen
                    </button>
                    <button
                      onClick={handleReset}
                      className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
                    >
                      Neue Datei
                    </button>
                  </div>
                </div>
              </div>
            )}

            {state === "error" && (
              <p className="text-sm text-red-600" role="alert">
                {errorMessage || "Fehler bei der Zusammenfassung"}
              </p>
            )}
          </div>
        </section>
      </div>
    </ProtectedRoute>
  );
}
