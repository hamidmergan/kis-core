"use client";

import { useCallback, useEffect, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import FileUpload from "@/components/jobs/FileUpload";
import GlossarySelector from "@/components/glossary/GlossarySelector";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import BackLink from "@/components/ui/BackLink";
import Spinner from "@/components/ui/Spinner";
import Select from "@/components/ui/Select";

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
        () => setStallMessage("Läuft noch - große Dokumente können einige Minuten dauern…"),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
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
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <section>
          <h1 className="text-xl font-bold mb-1">Übersetzung</h1>
          <p className="text-sm text-muted mb-6">
            Dokumente in andere Sprachen übersetzen. Layout und Formatierung bleiben erhalten.
          </p>

          <FileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />

          <div className="mt-6">
            <GlossarySelector values={glossaryIds} onChange={setGlossaryIds} />
          </div>

          {languages.length > 0 && (
            <div className="mb-4 flex items-center gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-foreground-soft mb-1">
                  Quellsprache
                </label>
                <Select
                  value={sourceLang}
                  onChange={(val) => {
                    setSourceLang(val);
                    if (val !== "auto" && val === targetLang) {
                      const other = languages.find((l) => l.id !== val);
                      if (other) setTargetLang(other.id);
                    }
                  }}
                  disabled
                  options={[{ value: "auto", label: "Automatisch erkennen" }, ...languages.map((l) => ({ value: l.id, label: l.label }))]}
                />
              </div>

              <div className="mt-5 text-muted-soft shrink-0">→</div>

              <div className="flex-1">
                <label className="block text-sm font-medium text-foreground-soft mb-1">
                  Zielsprache
                </label>
                <Select
                  value={targetLang}
                  onChange={(val) => {
                    setTargetLang(val);
                    if (sourceLang !== "auto" && val === sourceLang) {
                      const other = languages.find((l) => l.id !== val && l.id !== "auto");
                      if (other) setSourceLang(other.id);
                    }
                  }}
                  disabled
                  options={languages.map((l) => ({ value: l.id, label: l.label }))}
                />
              </div>
            </div>
          )}

          {providers.length > 0 && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-foreground-soft mb-1">
                Übersetzungs-Engine
              </label>
              <Select
                value={translationProvider}
                onChange={setTranslationProvider}
                disabled={processing}
                options={providers.map((p) => ({ value: p.id, label: p.label }))}
              />
            </div>
          )}

          {!doneJobUuid && (
            <div className="mb-6 flex items-center gap-3">
              <button
                onClick={handleSubmit}
                disabled={!pendingFile || processing}
                className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {processing && (
                  <Spinner size="sm" color="current" />
                )}
                {processing ? "Wird verarbeitet…" : "Übersetzen"}
              </button>
            </div>
          )}

          {stallMessage && !errorMessage && (
            <p className="text-sm text-warn" role="status">{stallMessage}</p>
          )}

          {errorMessage && (
            <p className="text-sm text-error" role="alert">{errorMessage}</p>
          )}

          {doneJobUuid && (
            <div className="mt-6 rounded-lg border border-border-soft bg-background p-6" role="status" aria-live="polite">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-sm font-medium text-foreground">Fertig! Download bereit</span>
                </div>
                {selectedFile && <p className="text-xs text-muted">{selectedFile}</p>}
                <div className="flex gap-3">
                  <button
                    onClick={handleDownload}
                    className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
                  >
                    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Übersetzung
                  </button>
                  <button
                    onClick={handleReset}
                    className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
                  >
                    Neue Datei
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </ProtectedRoute>
  );
}
