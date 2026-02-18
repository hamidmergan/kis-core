"use client";

import { useCallback, useState } from "react";
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
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [downloadName, setDownloadName] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const handleFileSelected = useCallback(
    async (file: File) => {
      setDownloadBlob(null);
      setDownloadName("");
      setErrorMessage("");
      setSelectedFile(file.name);
      setState("uploading");

      try {
        setState("translating");
        const glossaryJson = mergeToApiJson(glossaryIds);
        const fields: Record<string, string> = {};
        if (glossaryJson) fields.glossary = glossaryJson;
        const { blob, filename } = await api.uploadFileWithFields(
          "/translate",
          file,
          fields,
        );

        setDownloadBlob(blob);
        setDownloadName(filename);
        setState("done");
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
        setState("error");
      }
    },
    [glossaryIds, mergeToApiJson],
  );

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

          <h2 className="text-lg font-semibold text-gray-900 mb-1">Dokument übersetzen</h2>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie ein Dokument hoch, um es automatisch übersetzen zu lassen.
          </p>

          <GlossarySelector
            values={glossaryIds}
            onChange={setGlossaryIds}
          />

          <FileUpload
            onFileSelected={handleFileSelected}
            disabled={state === "uploading" || state === "translating"}
          />

          {selectedFile && state !== "idle" && (
            <p className="mt-3 text-xs text-gray-500">Datei: {selectedFile}</p>
          )}

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
