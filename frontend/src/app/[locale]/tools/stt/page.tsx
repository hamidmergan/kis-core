"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import TranscriptionFileUpload from "@/components/jobs/TranscriptionFileUpload";
import JobHistoryTable from "@/components/jobs/JobHistoryTable";
import { useJobHistory } from "@/hooks/useJobHistory";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import HelpTooltip from "@/components/ui/HelpTooltip";
import { stripAiNoticeVtt, withAiNoticeVtt } from "@/lib/aiNotice";

function formatFromFilename(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  return ext === "vtt" || ext === "srt" ? ext : "text";
}

function TranscriptionPageInner() {
  const t = useTranslations("tools.stt");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const verlauf = useJobHistory("transcription");
  // Only the jobs list links straight to one transcript.
  const ausListe = useSearchParams().get("job");
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
  const [transcriptText, setTranscriptText] = useState<string>("");
  const [transcriptFilename, setTranscriptFilename] = useState<string>("");
  // Long recordings run in parts, every finished part is reported.
  const [chunkProgress, setChunkProgress] = useState<{ current: number; total: number } | null>(null);

  const [responseFormat, setResponseFormat] = useState("text");

  // Reachable providers with a model, an empty list means hide the choice.
  const { providers, providerId, setProviderId } = useFeatureProviders("/transcription/providers");

  /** A finished transcript, fresh or from the history, loaded and shown the same way. */
  const ladeErgebnis = useCallback(async (jobUuid: string) => {
    setErrorMessage("");
    try {
      const { blob, filename } = await downloadJobAsBlob(jobUuid);
      const format = formatFromFilename(filename);
      const rawText = await blob.text();
      setResponseFormat(format);
      setTranscriptText(format === "vtt" ? stripAiNoticeVtt(rawText) : rawText);
      setTranscriptFilename(filename);
      setDoneJobUuid(jobUuid);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
    }
  }, [tCommon]);

  // Arriving from the jobs list: open straight on that one result.
  useEffect(() => {
    if (!ausListe) return;
    void ladeErgebnis(ausListe);
  }, [ausListe, ladeErgebnis]);

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
    setChunkProgress(null);
    try {
      const formData = new FormData();
      formData.append("file", pendingFile);
      formData.append("task", "transcribe");
      formData.append("response_format", responseFormat);
      if (providerId != null) formData.append("provider_id", String(providerId));
      const response = await backendApi.fetch("/transcription", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(
        data.job_uuid,
        (status) => {
          const p = status.progress as { step?: string; current?: number; total?: number } | null;
          if (p?.step === "transcribe" && typeof p.current === "number" && typeof p.total === "number") {
            setChunkProgress({ current: p.current, total: p.total });
          }
        },
        3000,
        undefined,
        () => setStallMessage(t("longRunning")),
        60_000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      // The finished transcript lands in the field, without a second trip to the server.
      const ext = responseFormat === "text" ? "txt" : responseFormat;
      const stem = pendingFile.name.replace(/\.[^.]+$/, "");
      const { blob, filename } = await downloadJobAsBlob(data.job_uuid, `${stem}.${ext}`);
      const rawText = await blob.text();
      setTranscriptText(responseFormat === "vtt" ? stripAiNoticeVtt(rawText) : rawText);
      setTranscriptFilename(filename);
      setDoneJobUuid(data.job_uuid);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setProcessing(false);
    }
  };

  const handleDownload = () => {
    if (!transcriptText) return;
    const content = responseFormat === "vtt" ? withAiNoticeVtt(transcriptText) : transcriptText;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = transcriptFilename || "transcript.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleReset = () => {
    setPendingFile(null);
    setSelectedFile("");
    setErrorMessage("");
    setDoneJobUuid(null);
    setTranscriptText("");
    setTranscriptFilename("");
  };

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 py-8">
        <ToolBackLink />
        <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
        <p className="text-sm text-muted mb-6">{t("intro")}</p>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,400px)_1fr]" data-tour="tool-transcription">
        <section className="min-w-0">
          <div>
            <TranscriptionFileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />
          </div>

          <ProviderSelect
            id="stt-provider-select"
            label={t("providerLabel")}
            providers={providers}
            value={providerId}
            onChange={setProviderId}
            disabled={processing}
            className="mt-6"
          />

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

          {stallMessage && !errorMessage && (
            <p className="text-sm text-warn" role="status">{stallMessage}</p>
          )}

          {errorMessage && (
            <p className="text-sm text-error" role="alert">{errorMessage}</p>
          )}
        </section>

        {/* The result, colored like the image tool's stage, always on the right. */}
        <section className="min-w-0">
          <div className="rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5" aria-live="polite">
            {processing ? (
              <div className="flex flex-col items-center justify-center gap-3 py-14 text-center">
                <Spinner label={chunkProgress ? t("chunkProgress", chunkProgress) : tCommon("processing")} />
                <BackgroundHint />
              </div>
            ) : doneJobUuid ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5 text-success shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-sm font-medium text-foreground">{t("readyTitle")}</span>
                  {transcriptFilename && <span className="text-xs text-muted truncate min-w-0">{transcriptFilename}</span>}
                </div>

                <textarea
                  value={transcriptText}
                  onChange={(e) => setTranscriptText(e.target.value)}
                  aria-label={t("editorAria")}
                  spellCheck={false}
                  className="w-full min-h-[16rem] sm:min-h-[28rem] resize-y rounded-md border border-border-soft bg-background px-3 py-2 text-sm leading-relaxed text-foreground-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
                />

                <div className="flex flex-wrap gap-3">
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
            ) : (
              <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
                <svg className="h-8 w-8 text-muted-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-sm text-foreground-soft">{t("resultPlaceholder")}</p>
              </div>
            )}
          </div>
        </section>
        </div>

        <div className="mt-10">
          <h2 className="text-sm font-semibold text-foreground mb-1">{t("history.title")}</h2>
          <p className="text-xs text-muted mb-3">{verlauf.length ? t("history.hint") : t("history.empty")}</p>
          {verlauf.length > 0 && (
            <JobHistoryTable
              entries={verlauf}
              selectedUuid={doneJobUuid}
              disabled={processing}
              locale={locale}
              colMaterial={t("history.colMaterial")}
              colDate={t("history.colDate")}
              onSelect={(uuid) => void ladeErgebnis(uuid)}
            />
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}

/** Wrapped so useSearchParams (the jobs-list link) has the Suspense boundary it needs. */
export default function TranscriptionPage() {
  return (
    <Suspense fallback={null}>
      <TranscriptionPageInner />
    </Suspense>
  );
}
