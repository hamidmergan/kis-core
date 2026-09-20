"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";
import Spinner from "@/components/ui/Spinner";
import Select from "@/components/ui/Select";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";

type Template = { slug: string; nameDe: string; nameEn: string; hintDe: string; hintEn: string };
type Setup = { templates: Template[]; maxSources: number; extensions: string[] };
type Progress = { step?: string; part?: number; total?: number } | null;

const FALLBACK_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".md", ".srt", ".vtt"];

export default function ZusammenfassungPage() {
  const t = useTranslations("tools.summarize");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  // Runs on the chat model, an empty list hides the choice.
  const { providers, providerId, setProviderId } = useFeatureProviders("/summary/providers");
  const [setup, setSetup] = useState<Setup | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [template, setTemplate] = useState("");
  const [processing, setProcessing] = useState(false);
  const [step, setStep] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const extensions = setup?.extensions ?? FALLBACK_EXTENSIONS;
  const maxSources = setup?.maxSources ?? 10;
  const templates = setup?.templates ?? [];
  const templateName = (v: Template) => (locale === "de" ? v.nameDe : v.nameEn);
  const templateHint = (v: Template) => (locale === "de" ? v.hintDe : v.hintEn);
  const chosen = templates.find((v) => v.slug === template);

  useEffect(() => {
    backendApi.fetch("/summary/templates")
      .then(async (r) => {
        if (!r.ok) return;
        const data = (await r.json()) as Setup;
        setSetup(data);
        if (data.templates[0]) setTemplate((v) => v || data.templates[0].slug);
      })
      .catch(() => {});
  }, []);

  const validateFile = useCallback((file: File): string | null => {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
    if (!extensions.includes(ext)) {
      return tCommon("onlyExtsAllowed", { exts: extensions.join(", ") });
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return tCommon("fileTooLarge", { n: MAX_UPLOAD_MB });
    }
    return null;
  }, [extensions, tCommon]);

  const addFiles = useCallback((neue: File[]) => {
    setUploadError(null);
    setDoneJobUuid(null);
    setErrorMessage("");
    setFiles((alt) => {
      const gesamt = [...alt];
      for (const f of neue) {
        const err = validateFile(f);
        if (err) { setUploadError(err); continue; }
        if (gesamt.length >= maxSources) {
          setUploadError(t("tooManySources", { max: maxSources }));
          break;
        }
        if (!gesamt.some((g) => g.name === f.name && g.size === f.size)) gesamt.push(f);
      }
      return gesamt;
    });
  }, [validateFile, maxSources, t]);

  const removeFile = (index: number) => setFiles((alt) => alt.filter((_, i) => i !== index));

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (processing) return;
      addFiles(Array.from(e.dataTransfer.files));
    },
    [processing, addFiles],
  );

  const handleSubmit = async () => {
    if (!files.length || processing) return;
    setProcessing(true);
    setErrorMessage("");
    setDoneJobUuid(null);
    setStep(t("step.extract"));
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      if (template) formData.append("template", template);
      if (providerId != null) formData.append("provider_id", String(providerId));
      const response = await backendApi.fetch("/summary", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(
        data.job_uuid,
        (status) => {
          const p = status.progress as Progress;
          if (!p?.step) return;
          // Zero done files reads as the plain sentence, never as "0 von 1".
          setStep(typeof p.part === "number" && typeof p.total === "number" && p.part > 0
            ? t(`step.${p.step}Counted`, { part: p.part, total: p.total })
            : t(`step.${p.step}`));
        },
        3000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      setDoneJobUuid(data.job_uuid);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setProcessing(false);
      setStep("");
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

  const handleDownloadDocx = async () => {
    if (!doneJobUuid) return;
    try {
      const { blob, filename } = await downloadJobAsBlob(doneJobUuid, "zusammenfassung.docx", "docx");
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
    setFiles([]);
    setDoneJobUuid(null);
    setErrorMessage("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const full = files.length >= maxSources;

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <ToolBackLink />
        <section data-tour="tool-summary">
          <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
          <p className="text-sm text-muted mb-6">{t("intro")}</p>

          <div
            role="button"
            tabIndex={0}
            aria-label={t("selectFileAria")}
            onClick={() => !processing && !full && inputRef.current?.click()}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !processing && !full) {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); if (!processing && !full) setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            className={[
              "border-2 border-dashed rounded-lg p-10 text-center transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb",
              dragActive ? "border-kb bg-info-bg" : files.length ? "border-kb60 bg-kb20" : "border-border hover:border-kb",
              processing || full ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
            ].join(" ")}
          >
            <p className="text-sm font-medium text-muted">
              {tCommon("dropOrBrowse")}{" "}
              <span className="text-kb underline">{tCommon("browse")}</span>
            </p>
            <p className="text-xs text-muted-soft mt-1">{extensions.join(", ")}</p>
          </div>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={extensions.join(",")}
            onChange={(e) => {
              addFiles(Array.from(e.target.files ?? []));
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="hidden"
            aria-hidden="true"
          />
          {uploadError && (
            <p className="mt-2 text-sm text-error" role="alert">{uploadError}</p>
          )}

          {files.length > 0 && (
            <div className="mt-4">
              <p className="text-sm font-medium text-foreground mb-2">{t("chosenFiles")}</p>
              <ul className="space-y-1">
                {files.map((f, i) => (
                  <li key={`${f.name}-${f.size}`} className="flex items-center justify-between text-sm text-foreground">
                    <span className="truncate">{f.name}</span>
                    {!processing && !doneJobUuid && (
                      <button
                        type="button"
                        onClick={() => removeFile(i)}
                        className="text-xs text-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
                      >
                        {t("removeFile")}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {templates.length > 0 && (
            <div className="mt-6">
              <label htmlFor="summary-template-select" className="block text-sm font-medium text-foreground mb-1">
                {t("templateLabel")}
              </label>
              <Select
                id="summary-template-select"
                value={template}
                onChange={setTemplate}
                disabled={processing}
                options={templates.map((v) => ({ value: v.slug, label: templateName(v) }))}
              />
              {chosen && <p className="mt-1 text-xs text-muted">{templateHint(chosen)}</p>}
            </div>
          )}

          <ProviderSelect
            id="summary-provider-select"
            label={t("providerLabel")}
            providers={providers}
            value={providerId}
            onChange={setProviderId}
            disabled={processing}
            className="mt-6"
          />

          {!doneJobUuid && (
            <div className="mt-6 flex items-center gap-3">
              <button
                onClick={handleSubmit}
                disabled={!files.length || processing}
                className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {processing && <Spinner size="sm" color="current" />}
                {processing ? tCommon("processing") : t("submit")}
              </button>
              {processing && step && (
                <span className="text-sm text-muted" role="status">{step}</span>
              )}
            </div>
          )}

          {processing && <BackgroundHint />}

          {errorMessage && (
            <p className="mt-3 text-sm text-error" role="alert">{errorMessage}</p>
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
                    onClick={handleDownloadDocx}
                    className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
                  >
                    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {t("downloadDocxLabel")}
                  </button>
                  <button
                    onClick={handleReset}
                    className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
                  >
                    {tCommon("newFile")}
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
