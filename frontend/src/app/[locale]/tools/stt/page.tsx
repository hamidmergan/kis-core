"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ErgebnisInfoKnopf, ErgebnisLoeschenKnopf, useErgebnisAngaben } from "@/components/jobs/ErgebnisInfo";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import StatusMark from "@/components/ui/StatusMark";
import TranscriptionFileUpload from "@/components/jobs/TranscriptionFileUpload";
import JobHistorySection from "@/components/jobs/JobHistorySection";
import { cancelJob } from "@/components/jobs/JobCancelButton";
import { useJobHistory } from "@/hooks/useJobHistory";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import HelpTooltip from "@/components/ui/HelpTooltip";
import { stripAiNoticeVtt, withAiNoticeVtt } from "@/lib/aiNotice";
import { DownloadButton, ResetButton } from "@/components/jobs/ResultButtons";
import JobSubmitRow from "@/components/jobs/JobSubmitRow";
import { triggerBlobDownload } from "@/lib/download";
import { notifyJobsChanged } from "@/lib/jobs-events";

function formatFromFilename(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  return ext === "vtt" || ext === "srt" ? ext : "text";
}

function TranscriptionPageInner() {
  const t = useTranslations("tools.stt");
  const tCommon = useTranslations("common");
  const tResult = useTranslations("common.result");
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
  const auftrag = useErgebnisAngaben(doneJobUuid);
  const [transcriptText, setTranscriptText] = useState<string>("");
  const [transcriptFilename, setTranscriptFilename] = useState<string>("");
  // Long recordings run in parts, every finished part is reported.
  const [chunkProgress, setChunkProgress] = useState<{ current: number; total: number } | null>(null);

  const [responseFormat, setResponseFormat] = useState("text");

  // Reachable providers with a model, an empty list means hide the choice.
  const { providers, providerId, setProviderId, loading: providersLoading } = useFeatureProviders("/transcription/providers");

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

  const abortRef = useRef<AbortController | null>(null);
  const jobUuidRef = useRef<string | null>(null);

  const handleCancel = () => {
    abortRef.current?.abort();
    cancelJob(jobUuidRef.current);
    jobUuidRef.current = null;
    setStallMessage("");
    setChunkProgress(null);
    setProcessing(false);
  };

  const handleSubmit = async () => {
    if (!pendingFile || processing) return;
    const controller = new AbortController();
    abortRef.current = controller;
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
      // A cancel during the upload stops the job as soon as its id is known.
      if (controller.signal.aborted) { cancelJob(data.job_uuid); return; }
      jobUuidRef.current = data.job_uuid;
      notifyJobsChanged();
      await pollJob(
        data.job_uuid,
        (status) => {
          const p = status.progress as { step?: string; current?: number; total?: number } | null;
          if (p?.step === "transcribe" && typeof p.current === "number" && typeof p.total === "number") {
            setChunkProgress({ current: p.current, total: p.total });
          }
        },
        3000,
        controller.signal,
        () => setStallMessage(t("longRunning")),
        60_000,
      );
      notifyJobsChanged();
      // The finished transcript lands in the field, without a second trip to the server.
      const ext = responseFormat === "text" ? "txt" : responseFormat;
      const stem = pendingFile.name.replace(/\.[^.]+$/, "");
      const { blob, filename } = await downloadJobAsBlob(data.job_uuid, `${stem}.${ext}`);
      const rawText = await blob.text();
      setTranscriptText(responseFormat === "vtt" ? stripAiNoticeVtt(rawText) : rawText);
      setTranscriptFilename(filename);
      setDoneJobUuid(data.job_uuid);
    } catch (err) {
      if (controller.signal.aborted) return;
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      if (abortRef.current === controller) setProcessing(false);
    }
  };

  const handleDownload = () => {
    if (!transcriptText) return;
    const content = responseFormat === "vtt" ? withAiNoticeVtt(transcriptText) : transcriptText;
    triggerBlobDownload(new Blob([content], { type: "text/plain;charset=utf-8" }), transcriptFilename || "transcript.txt");
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
        <section className="min-w-0 rounded-xl border border-border-soft bg-surface p-4 sm:p-5">
          <ProviderSelect
            id="stt-provider-select"
            label={t("providerLabel")}
            providers={providers}
            value={providerId}
            onChange={setProviderId}
            disabled={processing}
            loading={providersLoading}
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

          <JobSubmitRow
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            canSubmit={!!pendingFile}
            processing={processing}
            label={t("submit")}
            stallMessage={stallMessage}
            errorMessage={errorMessage}
          />
        </section>

        {/* The input on the right, the result takes its place once it is there. On the phone the input leads. */}
        <section className="min-w-0 order-first lg:order-none lg:col-start-2 lg:row-start-1">
          <div className="rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5" aria-live="polite">
            {processing ? (
              <>
                <BackgroundHint />
                <div className="flex flex-col items-center justify-center gap-3 py-14 text-center">
                  <Spinner label={chunkProgress ? t("chunkProgress", chunkProgress) : tCommon("processing")} />
                </div>
              </>
            ) : doneJobUuid ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <StatusMark tone="success" className="text-sm font-medium">{t("readyTitle")}</StatusMark>
                  {transcriptFilename && <span className="text-xs text-muted truncate min-w-0">{transcriptFilename}</span>}
                  <span className="ml-auto">
                    <ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
                      { label: tResult("file"), wert: auftrag?.datei },
                      { label: t("providerLabel"), wert: auftrag?.angaben.anbieter },
                      { label: t("outputFormat"), wert: FORMAT_OPTIONS.find((o) => o.value === auftrag?.angaben.format)?.label },
                    ]} />
                  </span>
                </div>

                <textarea
                  value={transcriptText}
                  onChange={(e) => setTranscriptText(e.target.value)}
                  aria-label={t("editorAria")}
                  spellCheck={false}
                  className="w-full min-h-[16rem] sm:min-h-[28rem] resize-y rounded-md border border-border-soft bg-background px-3 py-2 text-sm leading-relaxed text-foreground-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none"
                />

                <div className="flex flex-wrap gap-3">
                  <DownloadButton onClick={handleDownload} label={t("downloadLabel")} />
                  <ResetButton onClick={handleReset} label={t("newTranscript")} />
                  <ErgebnisLoeschenKnopf jobUuid={doneJobUuid} auftrag={auftrag} onGeloescht={handleReset} />
                </div>
              </div>
            ) : (
              <TranscriptionFileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />
            )}
          </div>
        </section>
        </div>

        <JobHistorySection
          namespace="tools.stt.history"
          entries={verlauf}
          selectedUuid={doneJobUuid}
          disabled={processing}
          onSelect={(uuid) => void ladeErgebnis(uuid)}
        />
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
