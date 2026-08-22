"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";
import Spinner from "@/components/ui/Spinner";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";

const ACCEPTED_EXTENSIONS = [".srt", ".vtt", ".txt", ".md", ".pptx", ".docx"];
const MAX_SIZE_MB = MAX_UPLOAD_MB;
const MAX_SIZE_BYTES = MAX_UPLOAD_BYTES;

export default function ZusammenfassungPage() {
  const t = useTranslations("tools.summarize");
  const tCommon = useTranslations("common");
  // Summary runs on the chat LLM; offer the reachable chat providers the admin
  // configured a model for. Empty list hides the dropdown (admin default route).
  const { providers, providerId, setProviderId } = useFeatureProviders("/summary/providers");
  const [processing, setProcessing] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);

  const [errorMessage, setErrorMessage] = useState("");
  const [stallMessage, setStallMessage] = useState("");

  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return tCommon("onlyExtsAllowed", { exts: ACCEPTED_EXTENSIONS.join(", ") });
    }
    if (file.size > MAX_SIZE_BYTES) {
      return tCommon("fileTooLarge", { n: MAX_SIZE_MB });
    }
    return null;
  };

  const handleFile = useCallback((file: File) => {
    setUploadError(null);
    const err = validateFile(file);
    if (err) { setUploadError(err); return; }
    setSelectedFile(file);
    setDoneJobUuid(null);
    setErrorMessage("");
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (processing) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [processing, handleFile],
  );

  const handleSubmit = async () => {
    if (!selectedFile || processing) return;
    setProcessing(true);
    setErrorMessage("");
    setStallMessage("");
    setDoneJobUuid(null);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      if (providerId != null) formData.append("provider_id", String(providerId));
      const response = await backendApi.fetch("/summary", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, `${tCommon("unknownError")}: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setStallMessage(t("longRunning")),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
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
    setSelectedFile(null);
    setDoneJobUuid(null);
    setErrorMessage("");
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
          <p className="text-sm text-muted mb-6">
            {t("intro")}
          </p>

          {/* File upload */}
          <div
            role="button"
            tabIndex={0}
            aria-label={t("selectFileAria")}
            onClick={() => !processing && inputRef.current?.click()}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !processing) {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); if (!processing) setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            className={[
              "border-2 border-dashed rounded-lg p-10 text-center transition-colors",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb",
              dragActive ? "border-kb bg-info-bg" : selectedFile ? "border-success-border bg-success-bg" : "border-border hover:border-kb",
              processing ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
            ].join(" ")}
          >
            {selectedFile ? (
              <>
                <svg className="mx-auto h-8 w-8 text-success mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <p className="text-sm font-medium text-foreground">{selectedFile.name}</p>
                <p className="text-xs text-muted-soft mt-1">{tCommon("clickToReplace")}</p>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-muted">
                  {tCommon("dropOrBrowse")}{" "}
                  <span className="text-kb underline">{tCommon("browse")}</span>
                </p>
                <p className="text-xs text-muted-soft mt-1">
                  {ACCEPTED_EXTENSIONS.join(", ")}
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
            <p className="mt-2 text-sm text-error" role="alert">{uploadError}</p>
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
                disabled={!selectedFile || processing}
                className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {processing && (
                  <Spinner size="sm" color="current" />
                )}
                {processing ? tCommon("processing") : t("submit")}
              </button>
            </div>
          )}

          {stallMessage && !errorMessage && (
            <p className="mt-3 text-sm text-warn" role="status">{stallMessage}</p>
          )}

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
                {selectedFile && <p className="text-xs text-muted">{selectedFile.name}</p>}
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
