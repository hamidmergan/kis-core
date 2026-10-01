"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ErgebnisInfoKnopf, ErgebnisLoeschenKnopf, useErgebnisAngaben } from "@/components/jobs/ErgebnisInfo";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import TtsFileUpload from "@/components/jobs/TtsFileUpload";
import TtsTextInput from "@/components/jobs/TtsTextInput";
import TtsStatus from "@/components/jobs/TtsStatus";
import JobHistoryTable from "@/components/jobs/JobHistoryTable";
import { useJobHistory } from "@/hooks/useJobHistory";
import { JobPausedError, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { TEXT_MODE_FILENAME, TTS_MAX_CHARS } from "@/lib/constants";
import type { TTSState } from "@/types";
import Select from "@/components/ui/Select";
import Tabs from "@/components/ui/Tabs";
import type { ProviderWithVoices } from "@/hooks/useVoices";
import OwnVoicesLink from "@/components/OwnVoicesLink";
import { preselectedVoice } from "@/hooks/_voiceDefault";
import { LANGUAGE_FLAG } from "@/lib/languageFlags";

type InputMode = "text" | "file";

function TtsPageInner() {
  const t = useTranslations("tools.tts");
  const tProgress = useTranslations("tools.tts.progress");
  const tCommon = useTranslations("common");
  const tResult = useTranslations("common.result");
  const locale = useLocale();
  const verlauf = useJobHistory("tts");
  // Only the jobs list links straight to one audio.
  const ausListe = useSearchParams().get("job");

  const [ttsState, setTtsState] = useState<TTSState>("idle");
  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [pendingText, setPendingText] = useState<string>("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [ttsSelectedFile, setTtsSelectedFile] = useState<string>("");
  const [ttsDownloadBlob, setTtsDownloadBlob] = useState<Blob | null>(null);
  const [ttsAudioUrl, setTtsAudioUrl] = useState<string>("");
  const [ttsDownloadName, setTtsDownloadName] = useState<string>("");
  const [ttsErrorMessage, setTtsErrorMessage] = useState<string>("");
  const [, setTtsProgressLabel] = useState<string>("");
  // Which history row the shown result belongs to, so that row can be highlighted.
  const [angezeigterJobUuid, setAngezeigterJobUuid] = useState<string | null>(null);

  // Providers loaded from /api/tts/providers-with-voices
  const [providers, setProviders] = useState<ProviderWithVoices[]>([]);
  const [providerId, setProviderId] = useState<number>(0);
  const [providersLoaded, setProvidersLoaded] = useState(false);

  // Voice selection
  const [voiceId, setVoiceId] = useState("");

  // Audio settings

  useEffect(() => {
    fetch("/api/tts/providers-with-voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const list: ProviderWithVoices[] = data.providers ?? [];
        setProviders(list);
        const vorauswahl = preselectedVoice(list, data.default);
        if (vorauswahl) {
          setProviderId(vorauswahl.providerId);
          if (vorauswahl.voiceId) setVoiceId(vorauswahl.voiceId);
        }
      })
      .catch(() => {
        // Provider check failed — leave all disabled, noProvider message will show.
      })
      .finally(() => {
        setProvidersLoaded(true);
      });
  }, []);

  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);
  // Kept across a pause, the file name must survive a cleared form.
  const dateiStammRef = useRef("text");

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); setTtsState("idle"); };
  }, []);

  // Expose the finished audio as a playable object URL (created/revoked with the blob).
  useEffect(() => {
    if (!ttsDownloadBlob) { setTtsAudioUrl(""); return; }
    const url = URL.createObjectURL(ttsDownloadBlob);
    setTtsAudioUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [ttsDownloadBlob]);

  const auftrag = useErgebnisAngaben(ttsState === "done" ? angezeigterJobUuid : null);
  const isProcessing = ttsState === "uploading" || ttsState === "processing";
  const noProvider = providersLoaded && providers.length === 0;

  /** A finished job, fresh or from the history, loaded the same way. */
  const ladeErgebnis = useCallback(async (jobUuid: string) => {
    setTtsErrorMessage("");
    try {
      const { blob, filename } = await downloadJobAsBlob(jobUuid, "tts.mp3");
      setTtsDownloadBlob(blob);
      setTtsDownloadName(filename);
      setAngezeigterJobUuid(jobUuid);
      setTtsState("done");
    } catch (err) {
      setTtsErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
      setTtsState("error");
    }
  }, [tCommon]);

  // Arriving from the jobs list: open straight on that one result.
  useEffect(() => {
    if (!ausListe) return;
    void ladeErgebnis(ausListe);
  }, [ausListe, ladeErgebnis]);

  const handleTtsFileSelected = useCallback((file: File) => {
    setPendingFile(file);
    setTtsSelectedFile(file.name);
    setTtsDownloadBlob(null);
    setTtsDownloadName("");
    setTtsErrorMessage("");
    setTtsState("idle");
    setAngezeigterJobUuid(null);
  }, []);

  const trimmedText = pendingText.trim();
  const textOverLimit = pendingText.length > TTS_MAX_CHARS;
  const canSubmit = inputMode === "file"
    ? !!pendingFile
    : trimmedText.length > 0 && !textOverLimit;

  const activeProvider = providers.find((p) => p.id === providerId);

  const handleSubmit = async () => {
    if (!canSubmit || isProcessing) return;

    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;
    setTtsState("uploading");
    setTtsProgressLabel(tProgress("uploading"));
    try {
      const activeVoice = activeProvider?.voices.find((v) => v.voice_id === voiceId);
      const voiceLabel = activeVoice
        ? `${LANGUAGE_FLAG[activeVoice.language] ?? ""} ${activeVoice.name}`.trim()
        : voiceId;

      const formData = new FormData();
      if (inputMode === "file" && pendingFile) {
        formData.append("file", pendingFile);
      } else {
        formData.append("text", pendingText);
      }
      formData.append("voice_id", voiceId);
      formData.append("voice_label", voiceLabel);
      formData.append("provider_id", String(providerId));

      const uploadRes = await fetch("/api/tts", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      dateiStammRef.current = inputMode === "file" && pendingFile
        ? pendingFile.name.replace(/\.[^.]+$/, "")
        : "text";
      await verfolgeJob(job_uuid, signal);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      currentJobUuidRef.current = null;
      setTtsErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
      setTtsState("error");
    }
  };

  /** Follows one job to the end and downloads it, used by the first run and by Weiter. */
  const verfolgeJob = async (job_uuid: string, signal: AbortSignal) => {
    setTtsState("processing");
    setTtsProgressLabel(tProgress("queued"));
    try {
      const jobResult = await pollJob(
        job_uuid,
        (status) => {
          const p = status.progress as { step?: string; chunk?: number; total?: number } | null;
          if (p?.step === "extract") setTtsProgressLabel(tProgress("extracting"));
          else if (p?.step === "synthesize" && p.chunk && p.total)
            setTtsProgressLabel(tProgress("synthesizingChunk", { chunk: p.chunk, total: p.total }));
          else if (p?.step === "synthesize") setTtsProgressLabel(tProgress("synthesizing"));
          else setTtsProgressLabel(tProgress("queued"));
        },
        3000,
        signal,
        () => setTtsProgressLabel(tProgress("noProgress")),
        60_000,
      );

      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      setTtsProgressLabel(tProgress("downloading"));
      const { blob, filename } = await downloadJobAsBlob(
        jobResult.job_uuid,
        `${dateiStammRef.current}.mp3`,
      );
      setTtsDownloadBlob(blob);
      setTtsDownloadName(filename);
      setAngezeigterJobUuid(jobResult.job_uuid);
      currentJobUuidRef.current = null;
      setTtsState("done");
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      // Paused keeps the job, the person decides whether it carries on.
      if (err instanceof JobPausedError) {
        currentJobUuidRef.current = err.jobUuid;
        setTtsErrorMessage(err.message);
        setTtsState("paused");
        return;
      }
      throw err;
    }
  };

  /** Weiter on a paused job: the finished pieces stay, only the rest is voiced. */
  const handleTtsContinue = async () => {
    const uuid = currentJobUuidRef.current;
    if (!uuid) return;
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    try {
      const res = await fetch(`/api/jobs/${uuid}/retry`, { method: "POST", credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      await verfolgeJob(uuid, abortControllerRef.current.signal);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setTtsErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
      setTtsState("error");
    }
  };

  const handleTtsDownload = () => {
    if (!ttsDownloadBlob) return;
    const url = URL.createObjectURL(ttsDownloadBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = ttsDownloadName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleTtsReset = () => {
    setTtsState("idle");
    setPendingFile(null);
    setPendingText("");
    setTtsSelectedFile("");
    setTtsDownloadBlob(null);
    setTtsDownloadName("");
    setTtsErrorMessage("");
    setTtsProgressLabel("");
    setAngezeigterJobUuid(null);
  };

  const handleModeChange = (mode: InputMode) => {
    if (isProcessing) return;
    setInputMode(mode);
    setTtsErrorMessage("");
    if (ttsState === "error") setTtsState("idle");
  };

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 py-8">
        <ToolBackLink />
        <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
        <p className="text-sm text-muted mb-6">{t("intro")}</p>

        {/* What goes in, above both columns like the tabs of the image tool. */}
        <Tabs
          className="mb-6"
          active={inputMode}
          onChange={(key) => handleModeChange(key as InputMode)}
          items={[
            { key: "text", label: t("inputMode.text"), disabled: isProcessing || noProvider },
            { key: "file", label: t("inputMode.file"), disabled: isProcessing || noProvider },
          ]}
        />

        <div className="grid gap-8 lg:grid-cols-[minmax(0,400px)_1fr]" data-tour="tool-tts">
        <section className="min-w-0 rounded-xl border border-border-soft bg-surface p-4 sm:p-5">
          {noProvider && (
            <p className="mb-4 text-sm text-muted-soft">{t("noProvider")}</p>
          )}

          {/* Provider */}
          {providersLoaded && providers.length > 1 && (
            <div className="mb-2">
              <label htmlFor="provider-select" className="block text-sm font-medium text-foreground-soft mb-2">
                {t("providerLabel")}
              </label>
              <Select
                id="provider-select"
                value={String(providerId)}
                onChange={(v) => {
                  const newId = Number(v);
                  setProviderId(newId);
                  const p = providers.find((x) => x.id === newId);
                  if (p && p.voices.length > 0) setVoiceId(p.voices[0].voice_id);
                }}
                disabled={isProcessing}
                options={providers.map((p) => ({ value: String(p.id), label: p.name }))}
              />
            </div>
          )}

          {/* Voice */}
          {providersLoaded && providers.length > 0 && (
            <div className="mt-4 mb-6 space-y-3">
              <div>
                <label htmlFor="voice-select" className="block text-sm font-medium text-foreground-soft mb-2">
                  {t("voiceLabel")}
                </label>
                <Select
                  id="voice-select"
                  value={voiceId}
                  onChange={setVoiceId}
                  disabled={isProcessing}
                  options={(activeProvider?.voices ?? []).map((v) => ({
                    value: v.voice_id,
                    label: `${LANGUAGE_FLAG[v.language] ?? ""} ${v.name}${v.description ? ` — ${v.description}` : ""}`.trim(),
                  }))}
                />
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                <a
                  href="/tools/tts/voices"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-kb hover:underline"
                >
                  {t("previewVoices")}
                </a>
                <OwnVoicesLink />
              </div>
            </div>
          )}


          {ttsState !== "done" && (
            <div className="mb-6 flex items-center gap-3">
              <button
                onClick={handleSubmit}
                disabled={!canSubmit || isProcessing || noProvider}
                className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("submit")}
              </button>
              {isProcessing && (
                <button
                  onClick={() => {
                    const uuid = currentJobUuidRef.current;
                    currentJobUuidRef.current = null;
                    abortControllerRef.current?.abort();
                    if (uuid) { fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {}); window.dispatchEvent(new CustomEvent("kis-jobs-changed")); }
                    setTtsState("idle");
                  }}
                  className="btn-cancel px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  {t("cancel")}
                </button>
              )}
            </div>
          )}
        </section>

        {/* The input on the right, the result takes its place once it is there. On the phone the input leads. */}
        <section className="min-w-0 order-first lg:order-none lg:col-start-2 lg:row-start-1">
          <div className="rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5" aria-live="polite">
            {ttsState === "idle" ? (
              inputMode === "text" ? (
                <TtsTextInput value={pendingText} onChange={setPendingText} disabled={noProvider} />
              ) : (
                <TtsFileUpload onFileSelected={handleTtsFileSelected} disabled={noProvider}
                  selectedFilename={ttsSelectedFile || undefined} />
              )
            ) : (
              <TtsStatus
                state={ttsState}
                fileName={ttsDownloadName}
                audioUrl={ttsAudioUrl}
                errorMessage={ttsErrorMessage}
                onDownload={handleTtsDownload}
                onReset={handleTtsReset}
                onRetry={() => { setTtsState("idle"); setTtsErrorMessage(""); }}
                onContinue={handleTtsContinue}
                info={<ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
                  { label: tResult("file"), wert: auftrag?.datei !== TEXT_MODE_FILENAME ? auftrag?.datei : null },
                  { label: tResult("provider"), wert: auftrag?.angaben.anbieter },
                  { label: t("voiceLabel"), wert: auftrag?.angaben.stimme },
                ]} />}
                loeschen={angezeigterJobUuid && (
                  <ErgebnisLoeschenKnopf jobUuid={angezeigterJobUuid} auftrag={auftrag} onGeloescht={handleTtsReset} />
                )}
              />
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
              selectedUuid={angezeigterJobUuid}
              disabled={isProcessing}
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
export default function TtsPage() {
  return (
    <Suspense fallback={null}>
      <TtsPageInner />
    </Suspense>
  );
}
