"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import FileUpload from "@/components/FileUpload";
import GlossarySelector from "@/components/GlossarySelector";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";

export default function UebersetzungPage() {
  const { mergeToApiJson } = useGlossaries();
  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);

  const [processing, setProcessing] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [stallMessage, setStallMessage] = useState<string>("");
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);

  const [providers, setProviders] = useState<{ id: string; label: string }[]>([]);
  const [languages, setLanguages] = useState<{ id: string; label: string }[]>([]);
  const [translationProvider, setTranslationProvider] = useState<string>("");
  const [sourceLang, setSourceLang] = useState<string>("DE");
  const [targetLang, setTargetLang] = useState<string>("");

  useEffect(() => {
    api
      .fetch("/translate/config")
      .then((r) => r.json())
      .then((data) => {
        setProviders(data.providers ?? []);
        setLanguages(data.languages ?? []);
        setTranslationProvider(data.default_provider ?? "");
        setSourceLang(data.default_source ?? "DE");
        setTargetLang(data.default_target ?? "");
      })
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
      const glossaryJson = mergeToApiJson(glossaryIds);
      const formData = new FormData();
      formData.append("file", pendingFile);
      if (glossaryJson) formData.append("glossary", glossaryJson);
      if (translationProvider) formData.append("translation_provider", translationProvider);
      if (sourceLang && sourceLang !== "auto") formData.append("source_lang", sourceLang);
      if (targetLang) formData.append("target_lang", targetLang);
      const response = await api.fetch("/translate", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setStallMessage("Läuft noch – große Dokumente können einige Minuten dauern…"),
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
          <h1 className="text-xl font-bold text-gray-900 mb-1">Translate</h1>
          <p className="text-sm text-gray-500 mb-6">
            Übersetzen Sie Dokumente automatisch von Deutsch nach Englisch.
          </p>

          <FileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />

          <div className="mt-6">
            <GlossarySelector values={glossaryIds} onChange={setGlossaryIds} />
          </div>

          {languages.length > 0 && (
            <div className="mb-4 flex items-center gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Quellsprache
                </label>
                <select
                  value={sourceLang}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSourceLang(val);
                    if (val !== "auto" && val === targetLang) {
                      const other = languages.find((l) => l.id !== val);
                      if (other) setTargetLang(other.id);
                    }
                  }}
                  disabled
                  className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-[#004261] focus:ring-1 focus:ring-[#004261] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <option value="auto">Automatisch erkennen</option>
                  {languages.map((l) => (
                    <option key={l.id} value={l.id}>{l.label}</option>
                  ))}
                </select>
              </div>

              <div className="mt-5 text-gray-400 shrink-0">→</div>

              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Zielsprache
                </label>
                <select
                  value={targetLang}
                  onChange={(e) => {
                    const val = e.target.value;
                    setTargetLang(val);
                    if (sourceLang !== "auto" && val === sourceLang) {
                      const other = languages.find((l) => l.id !== val && l.id !== "auto");
                      if (other) setSourceLang(other.id);
                    }
                  }}
                  disabled
                  className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-[#004261] focus:ring-1 focus:ring-[#004261] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {languages.map((l) => (
                    <option key={l.id} value={l.id}>{l.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {providers.length > 0 && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Übersetzungs-Engine
              </label>
              <select
                value={translationProvider}
                onChange={(e) => setTranslationProvider(e.target.value)}
                disabled={processing}
                className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-[#004261] focus:ring-1 focus:ring-[#004261] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>
          )}

          <div className="mb-6 flex items-center gap-3">
            <button
              onClick={handleSubmit}
              disabled={!pendingFile || processing}
              className="self-start px-5 py-2 bg-[#004261] text-white text-sm font-medium rounded-md hover:bg-[#003a56] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004261] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {processing && (
                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
              )}
              {processing ? "Wird verarbeitet…" : "Übersetzen"}
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
                Übersetzung
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
