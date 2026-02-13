"use client";

import { useCallback, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import FileUpload from "@/components/FileUpload";
import TranslationStatus from "@/components/TranslationStatus";
import GlossaryPanel from "@/components/GlossaryPanel";
import type { GlossaryEntry } from "@/components/GlossaryPanel";
import { api } from "@/lib/api";
import type { TranslationState } from "@/types";

type Tab = "translate" | "glossary";

export default function UebersetzungPage() {
  const [tab, setTab] = useState<Tab>("translate");

  // Glossary state
  const [glossaryEntries, setGlossaryEntries] = useState<GlossaryEntry[]>([]);

  // Translation state
  const [state, setState] = useState<TranslationState>("idle");
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [downloadName, setDownloadName] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const glossaryAsRecord = (): Record<string, string> => {
    const map: Record<string, string> = {};
    for (const entry of glossaryEntries) {
      if (entry.source.trim() && entry.target.trim()) {
        map[entry.source.trim()] = entry.target.trim();
      }
    }
    return map;
  };

  const handleFileSelected = useCallback(
    async (file: File) => {
      setDownloadBlob(null);
      setDownloadName("");
      setErrorMessage("");
      setSelectedFile(file.name);
      setState("uploading");

      try {
        setState("translating");
        const { blob, filename } = await api.uploadFile(
          "/translate",
          file,
          glossaryAsRecord(),
        );

        setDownloadBlob(blob);
        setDownloadName(filename);
        setState("done");
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
        setState("error");
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [glossaryEntries],
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

  const tabs = [
    { id: "translate" as Tab, label: "Übersetzen" },
    { id: "glossary" as Tab, label: `Glossar${glossaryEntries.length > 0 ? ` (${glossaryEntries.length})` : ""}` },
  ];

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Dokumentenübersetzung</h1>
          <p className="text-sm text-gray-500 mb-6">
            Übersetzen Sie Dokumente automatisch von Deutsch nach Englisch.
          </p>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-gray-200 mb-8">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                  tab === t.id
                    ? "border-[#0066cc] text-[#0066cc]"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {tab === "translate" && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-1">Dokument übersetzen</h2>
              <p className="text-sm text-gray-500 mb-6">
                Laden Sie ein Dokument hoch, um es automatisch übersetzen zu lassen.
              </p>

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
            </div>
          )}

          {tab === "glossary" && (
            <GlossaryPanel entries={glossaryEntries} onChange={setGlossaryEntries} />
          )}
        </section>
      </div>
    </ProtectedRoute>
  );
}
