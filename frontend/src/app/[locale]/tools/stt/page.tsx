"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import TranscriptionFileUpload from "@/components/jobs/TranscriptionFileUpload";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import BackLink from "@/components/ui/BackLink";
import Spinner from "@/components/ui/Spinner";
import HelpTooltip from "@/components/ui/HelpTooltip";

export default function TranscriptionPage() {
  const t = useTranslations("tools.stt");
  const tCommon = useTranslations("common");
  const FORMAT_OPTIONS = [
    { value: "text", label: t("format.text") },
    { value: "srt", label: t("format.srt") },
    { value: "vtt", label: t("format.vtt") },
  ];
  const [processing, setProcessing] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [stallMessage, setStallMessage] = useState<string>("");
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);

  const [responseFormat, setResponseFormat] = useState("text");

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
      const formData = new FormData();
      formData.append("file", pendingFile);
      formData.append("task", "transcribe");
      formData.append("response_format", responseFormat);
      const response = await backendApi.fetch("/transcription", { method: "POST", body: formData });
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
          <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
          <p className="text-sm text-muted mb-6">
            {t("intro")}
          </p>

          <TranscriptionFileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />

          <div className="mb-6 mt-6">
            <span className="flex items-center gap-1.5 text-sm font-medium text-foreground-soft mb-2">
              {t("outputFormat")}
              <HelpTooltip text={t("outputFormatHelp")} />
            </span>
            <div className="flex gap-6">
              {FORMAT_OPTIONS.map((opt) => (
                <label key={opt.value} className="group flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="response-format"
                    value={opt.value}
                    checked={responseFormat === opt.value}
                    onChange={() => setResponseFormat(opt.value)}
                    disabled={processing}
                    className="appearance-none w-4 h-4 rounded-full border-2 border-muted group-hover:border-[var(--kb)] checked:border-[var(--kb)] checked:bg-[var(--kb)] checked:shadow-[inset_0_0_0_2px_white] transition-colors cursor-pointer"
                  />
                  <span className="text-sm text-foreground-soft group-hover:text-[var(--kb)]">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {!doneJobUuid && (
            <div className="mb-6">
              <button
                onClick={handleSubmit}
                disabled={!pendingFile || processing}
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
