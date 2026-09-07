"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Copy, Check } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import FileUpload from "@/components/jobs/FileUpload";
import TranslateTextInput from "@/components/jobs/TranslateTextInput";
import GlossarySelector from "@/components/glossary/GlossarySelector";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { copyTextFromPromise } from "@/lib/clipboard";
import Spinner from "@/components/ui/Spinner";
import Select from "@/components/ui/Select";
import Tabs from "@/components/ui/Tabs";
import { TRANSLATE_MAX_CHARS } from "@/lib/constants";

type InputMode = "text" | "file";

export default function UebersetzungPage() {
  const t = useTranslations("tools.translate");
  const tCommon = useTranslations("common");
  const { mergeToApiJson } = useGlossaries();
  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);

  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [pendingText, setPendingText] = useState<string>("");
  const [processing, setProcessing] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [stallMessage, setStallMessage] = useState<string>("");
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);
  const [translatedText, setTranslatedText] = useState<string>("");
  const [translatedSourceText, setTranslatedSourceText] = useState<string>("");
  const [copied, setCopied] = useState(false);

  const [providers, setProviders] = useState<{ id: number; label: string }[]>([]);
  const [languages, setLanguages] = useState<{ id: string; label: string }[]>([]);
  const [translationProviderId, setTranslationProviderId] = useState<number | null>(null);
  const [targetLang, setTargetLang] = useState<string>("");

  useEffect(() => {
    api
      .fetch("/translate/config")
      .then((r) => r.json())
      .then((data) => {
        const provs: { id: number; label: string }[] = data.providers ?? [];
        setProviders(provs);
        setLanguages(data.languages ?? []);
        if (provs.length > 0) setTranslationProviderId(provs[0].id);
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

  const trimmedText = pendingText.trim();
  const textOverLimit = pendingText.length > TRANSLATE_MAX_CHARS;
  const canSubmit = inputMode === "file"
    ? !!pendingFile
    : trimmedText.length > 0 && !textOverLimit;
  const resultStale = !!translatedText && pendingText !== translatedSourceText;

  const handleModeChange = (mode: InputMode) => {
    if (processing) return;
    setInputMode(mode);
    setErrorMessage("");
    setDoneJobUuid(null);
  };

  const handleSubmit = async () => {
    if (!canSubmit || processing) return;
    setProcessing(true);
    setErrorMessage("");
    setStallMessage("");
    setDoneJobUuid(null);
    setTranslatedText("");
    try {
      const glossaryJson = mergeToApiJson(glossaryIds);
      const formData = new FormData();
      if (inputMode === "file" && pendingFile) {
        formData.append("file", pendingFile);
      } else {
        formData.append("text", pendingText);
      }
      if (glossaryJson) formData.append("glossary", glossaryJson);
      if (translationProviderId != null) formData.append("provider_id", String(translationProviderId));
      // Source language is always auto-detected (no source_lang sent).
      if (targetLang) formData.append("target_lang", targetLang);
      const response = await api.fetch("/translate", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setStallMessage(t("longRunning")),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      if (inputMode === "text") {
        try {
          const { blob } = await downloadJobAsBlob(data.job_uuid, "text.txt");
          setTranslatedText(await blob.text());
          setTranslatedSourceText(pendingText);
        } catch {
          // Preview is a bonus, the download button below still works.
        }
      }
      setDoneJobUuid(data.job_uuid);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
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
      setErrorMessage(err instanceof Error ? err.message : tCommon("downloadFailed"));
    }
  };

  const handleReset = () => {
    setPendingFile(null);
    setPendingText("");
    setSelectedFile("");
    setErrorMessage("");
    setDoneJobUuid(null);
    setTranslatedText("");
    setTranslatedSourceText("");
  };

  const handleCopy = () => {
    if (!translatedText) return;
    copyTextFromPromise(Promise.resolve(translatedText));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <section data-tour="tool-translation">
          <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
          <p className="text-sm text-muted mb-6">
            {t("intro")}
          </p>

          <div className="mb-4">
            <Tabs
              variant="pill"
              active={inputMode}
              onChange={(key) => handleModeChange(key as InputMode)}
              items={[
                { key: "text", label: t("inputMode.text"), disabled: processing },
                { key: "file", label: t("inputMode.file"), disabled: processing },
              ]}
            />
          </div>

          <div>
          {inputMode === "text" ? (
            <TranslateTextInput
              value={pendingText}
              onChange={setPendingText}
              disabled={processing}
            />
          ) : (
            <FileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />
          )}
          </div>

          {languages.length > 0 && (
            <div className="mb-4 mt-6">
              <label className="block text-sm font-medium text-foreground-soft mb-1">
                {t("targetLang")}
              </label>
              <Select
                value={targetLang}
                onChange={setTargetLang}
                disabled={processing}
                options={languages.map((l) => ({ value: l.id, label: l.label }))}
              />
              <p className="mt-1 text-xs text-muted">{t("autoDetectHint")}</p>
            </div>
          )}

          <GlossarySelector values={glossaryIds} onChange={setGlossaryIds} />

          {providers.length > 1 && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-foreground-soft mb-1">
                {t("engine")}
              </label>
              <Select
                value={translationProviderId != null ? String(translationProviderId) : ""}
                onChange={(v) => setTranslationProviderId(v ? Number(v) : null)}
                disabled={processing}
                options={providers.map((p) => ({ value: String(p.id), label: p.label }))}
              />
            </div>
          )}

          <div className="mb-6 flex items-center gap-3">
            <button
              onClick={handleSubmit}
              disabled={!canSubmit || processing}
              className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {processing && (
                <Spinner size="sm" color="current" />
              )}
              {processing ? tCommon("processing") : t("submit")}
            </button>
          </div>

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
                  <span className="text-sm font-medium text-foreground">{tCommon("downloadReady")}</span>
                </div>
                {selectedFile && <p className="text-xs text-muted">{selectedFile}</p>}
                {translatedText && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-foreground-soft">{t("resultLabel")}</span>
                      <button
                        onClick={handleCopy}
                        className="p-1 rounded-full btn-icon"
                        title={copied ? t("copied") : t("copyText")}
                        aria-label={copied ? t("copied") : t("copyText")}
                      >
                        {copied ? <Check size={14} weight="bold" className="text-success" /> : <Copy size={14} />}
                      </button>
                    </div>
                    {resultStale && (
                      <p className="mb-1 text-xs text-warn">{t("resultStale")}</p>
                    )}
                    <div
                      className={`max-h-96 overflow-y-auto rounded-md border border-border px-3 py-2 text-sm text-foreground whitespace-pre-wrap transition-opacity ${resultStale ? "opacity-50" : ""}`}
                    >
                      {translatedText}
                    </div>
                  </div>
                )}
                <div className="flex gap-3">
                  <button
                    onClick={handleDownload}
                    className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
                  >
                    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {t("downloadLabel")}
                  </button>
                  <button
                    onClick={handleReset}
                    className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
                  >
                    {t("resetLabel")}
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
