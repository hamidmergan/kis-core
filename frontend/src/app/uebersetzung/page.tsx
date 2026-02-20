"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import FileUpload from "@/components/FileUpload";
import TranslationStatus from "@/components/TranslationStatus";
import GlossarySelector from "@/components/GlossarySelector";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api } from "@/lib/api";
import type { TranslationState } from "@/types";

export default function UebersetzungPage() {
  const { mergeToApiJson } = useGlossaries();
  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);

  const [state, setState] = useState<TranslationState>("idle");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [downloadName, setDownloadName] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); setState("idle"); };
  }, []);

  const isProcessing = state === "uploading" || state === "translating";

  const handleFileSelected = useCallback((file: File) => {
    setPendingFile(file);
    setSelectedFile(file.name);
    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
    setState("idle");
  }, []);

  const handleSubmit = async () => {
    if (!pendingFile || isProcessing) return;
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;
    setState("uploading");
    try {
      setState("translating");
      const glossaryJson = mergeToApiJson(glossaryIds);
      const fields: Record<string, string> = {};
      if (glossaryJson) fields.glossary = glossaryJson;
      const { blob, filename } = await api.uploadFileWithFields(
        "/translate",
        pendingFile,
        fields,
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
    setPendingFile(null);
    setSelectedFile("");
    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Dokumentenübersetzung</h1>
          <p className="text-sm text-gray-500 mb-6">
            Übersetzen Sie Dokumente automatisch von Deutsch nach Englisch.
          </p>

          <FileUpload
            onFileSelected={handleFileSelected}
            disabled={isProcessing}
          />
          {selectedFile && (
            <p className="mt-2 text-sm font-medium text-gray-700">{selectedFile}</p>
          )}

          <div className="mt-6">
            <GlossarySelector
              values={glossaryIds}
              onChange={setGlossaryIds}
            />
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
              {isProcessing ? "Übersetzung läuft…" : "Übersetzen"}
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

          <TranslationStatus
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
