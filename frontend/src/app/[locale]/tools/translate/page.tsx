"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Copy, Check } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import StatusMark from "@/components/ui/StatusMark";
import FileUpload from "@/components/jobs/FileUpload";
import TranslateTextInput from "@/components/jobs/TranslateTextInput";
import { ErgebnisInfoKnopf, ErgebnisLoeschenKnopf, useErgebnisAngaben } from "@/components/jobs/ErgebnisInfo";
import JobHistorySection from "@/components/jobs/JobHistorySection";
import { cancelJob } from "@/components/jobs/JobCancelButton";
import GlossarySelector from "@/components/glossary/GlossarySelector";
import { useGlossaries } from "@/hooks/useGlossaries";
import { useJobHistory } from "@/hooks/useJobHistory";
import { api, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { copyTextFromPromise } from "@/lib/clipboard";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import Select from "@/components/ui/Select";
import ProviderSelect, { LoadingField } from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import Tabs from "@/components/ui/Tabs";
import { TEXT_MODE_FILENAME, TRANSLATE_MAX_CHARS } from "@/lib/constants";
import { DownloadButton, ResetButton } from "@/components/jobs/ResultButtons";
import JobSubmitRow from "@/components/jobs/JobSubmitRow";
import { triggerBlobDownload } from "@/lib/download";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { appendFile } from "@/lib/directUpload";

type InputMode = "text" | "file";

function UebersetzungPageInner() {
  const t = useTranslations("tools.translate");
  const tCommon = useTranslations("common");
  const tResult = useTranslations("common.result");
  const { mergeToApiJson } = useGlossaries();
  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const verlauf = useJobHistory("translation");
  // Only the jobs list links straight to one translation.
  const ausListe = useSearchParams().get("job");

  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [pendingText, setPendingText] = useState<string>("");
  const [processing, setProcessing] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [stallMessage, setStallMessage] = useState<string>("");
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);
  const [translatedText, setTranslatedText] = useState<string>("");
  const [copied, setCopied] = useState(false);

  const { providers, providerId: translationProviderId, setProviderId: setTranslationProviderId,
    loading: providersLoading } = useFeatureProviders("/translate/providers");
  const [languages, setLanguages] = useState<{ id: string; label: string }[]>([]);
  const [targetLang, setTargetLang] = useState<string>("");
  const [languagesLoading, setLanguagesLoading] = useState(true);

  // Languages come right away, the providers load on their own.
  useEffect(() => {
    api
      .fetch("/translate/languages")
      .then((r) => r.json())
      .then((data) => {
        setLanguages(data.languages ?? []);
        setTargetLang(data.default_target ?? "");
      })
      .catch(() => {})
      .finally(() => setLanguagesLoading(false));
  }, []);

  // Arriving from the jobs list: open straight on that one result.
  useEffect(() => {
    if (!ausListe) return;
    setDoneJobUuid(ausListe);
    setErrorMessage("");
  }, [ausListe]);

  // The job this result belongs to, once it shows up in the history, tells us its real name.
  const aktiverVerlaufseintrag = verlauf.find((v) => v.job_uuid === doneJobUuid);
  // Text mode always saves under the same marker name, a real upload never does.
  const istTextErgebnis = aktiverVerlaufseintrag
    ? aktiverVerlaufseintrag.original_filename === TEXT_MODE_FILENAME
    : inputMode === "text";

  // The finished text, fetched once so a jumped-to or history-opened result reads straight on the page.
  useEffect(() => {
    if (!doneJobUuid || !istTextErgebnis) return;
    let abgelaufen = false;
    (async () => {
      try {
        const { blob } = await downloadJobAsBlob(doneJobUuid, TEXT_MODE_FILENAME);
        if (!abgelaufen) setTranslatedText(await blob.text());
      } catch {
        // Preview is a bonus, the download button below still works.
      }
    })();
    return () => { abgelaufen = true; };
  }, [doneJobUuid, istTextErgebnis]);

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
  // The real name of what is shown on the right, not what the left form happens to hold right now.
  const angezeigterDateiname = aktiverVerlaufseintrag?.original_filename ?? (doneJobUuid ? selectedFile : "");
  const auftrag = useErgebnisAngaben(doneJobUuid);

  const handleModeChange = (mode: InputMode) => {
    if (processing) return;
    setInputMode(mode);
    setErrorMessage("");
    setDoneJobUuid(null);
  };

  const abortRef = useRef<AbortController | null>(null);
  const jobUuidRef = useRef<string | null>(null);

  const handleCancel = () => {
    abortRef.current?.abort();
    cancelJob(jobUuidRef.current);
    jobUuidRef.current = null;
    setStallMessage("");
    setProcessing(false);
  };

  const handleSubmit = async () => {
    if (!canSubmit || processing) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setProcessing(true);
    setErrorMessage("");
    setStallMessage("");
    setDoneJobUuid(null);
    setTranslatedText("");
    try {
      const glossaryJson = mergeToApiJson(glossaryIds);
      const formData = new FormData();
      let forgetUpload = () => {};
      if (inputMode === "file" && pendingFile) {
        // A large document goes in parts straight into the bucket, a small one with the request.
        forgetUpload = await appendFile(formData, {
          tool: "translation", file: pendingFile, failedText: tCommon("unknownError"), signal: controller.signal,
        });
      } else {
        formData.append("text", pendingText);
      }
      if (glossaryJson) formData.append("glossary", glossaryJson);
      if (translationProviderId != null) formData.append("provider_id", String(translationProviderId));
      // Source language is always auto-detected (no source_lang sent).
      if (targetLang) formData.append("target_lang", targetLang);
      const response = await api.fetch("/translate", { method: "POST", body: formData });
      forgetUpload();
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const data = await response.json();
      // A cancel during the upload stops the job as soon as its id is known.
      if (controller.signal.aborted) { cancelJob(data.job_uuid); return; }
      jobUuidRef.current = data.job_uuid;
      notifyJobsChanged();
      await pollJob(data.job_uuid, undefined, 3000, controller.signal,
        () => setStallMessage(t("longRunning")),
        60_000,
      );
      notifyJobsChanged();
      setDoneJobUuid(data.job_uuid);
    } catch (err) {
      if (controller.signal.aborted) return;
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      if (abortRef.current === controller) setProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!doneJobUuid) return;
    try {
      const { blob, filename } = await downloadJobAsBlob(doneJobUuid);
      triggerBlobDownload(blob, filename);
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
  };

  const handleCopy = () => {
    if (!translatedText) return;
    copyTextFromPromise(Promise.resolve(translatedText));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
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
            { key: "text", label: t("inputMode.text"), disabled: processing },
            { key: "file", label: t("inputMode.file"), disabled: processing },
          ]}
        />

        <div className="grid gap-8 lg:grid-cols-[minmax(0,400px)_1fr]" data-tour="tool-translation">
        <section className="min-w-0 rounded-xl border border-border-soft bg-surface p-4 sm:p-5">
          {languagesLoading ? (
            <div className="mb-4">
              <label className="block text-sm font-medium text-foreground-soft mb-1">
                {t("targetLang")}
              </label>
              <LoadingField />
            </div>
          ) : languages.length > 0 && (
            <div className="mb-4">
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

          <ProviderSelect id="translate-provider-select" label={t("engine")} providers={providers}
            value={translationProviderId} onChange={setTranslationProviderId} disabled={processing}
            loading={providersLoading} />

          <JobSubmitRow
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            canSubmit={!!canSubmit}
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
                  <Spinner label={tCommon("processing")} />
                </div>
              </>
            ) : doneJobUuid ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <StatusMark tone="success" className="text-sm font-medium">{tCommon("downloadReady")}</StatusMark>
                  <ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
                  { label: tResult("file"), wert: angezeigterDateiname !== TEXT_MODE_FILENAME ? angezeigterDateiname : null },
                  { label: t("engine"), wert: auftrag?.angaben.anbieter },
                  { label: t("targetLang"), wert: auftrag?.angaben.ziel && (languages.find((l) => l.id === auftrag.angaben.ziel)?.label ?? auftrag.angaben.ziel) },
                  { label: tResult("glossary"), wert: auftrag?.angaben.glossar ? tResult("glossaryUsed") : null },
                  ]} />
                </div>
                {istTextErgebnis && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-foreground-soft">{t("resultLabel")}</span>
                      {translatedText && (
                        <button
                          onClick={handleCopy}
                          className="p-1 rounded-full btn-icon"
                          title={copied ? t("copied") : t("copyText")}
                          aria-label={copied ? t("copied") : t("copyText")}
                        >
                          {copied ? <Check size={14} weight="bold" className="text-success" /> : <Copy size={14} />}
                        </button>
                      )}
                    </div>
                    <div className="max-h-[28rem] overflow-y-auto rounded-md border border-border-soft bg-background px-3 py-2 text-sm text-foreground whitespace-pre-wrap">
                      {translatedText || <Spinner className="justify-center py-6" />}
                    </div>
                  </div>
                )}
                <div className="flex flex-wrap gap-3">
                  <DownloadButton onClick={handleDownload} label={t("downloadLabel")} />
                  <ResetButton onClick={handleReset} label={t("newTranslation")} />
                  <ErgebnisLoeschenKnopf jobUuid={doneJobUuid} auftrag={auftrag} onGeloescht={handleReset} />
                </div>
              </div>
            ) : inputMode === "text" ? (
              <TranslateTextInput value={pendingText} onChange={setPendingText} disabled={processing} />
            ) : (
              <FileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />
            )}
          </div>
        </section>
        </div>

        <JobHistorySection
          namespace="tools.translate.history"
          entries={verlauf}
          selectedUuid={doneJobUuid}
          disabled={processing}
          onSelect={(uuid) => { setDoneJobUuid(uuid); setErrorMessage(""); }}
        />
      </div>
    </ProtectedRoute>
  );
}

/** Wrapped so useSearchParams (the jobs-list link) has the Suspense boundary it needs. */
export default function UebersetzungPage() {
  return (
    <Suspense fallback={null}>
      <UebersetzungPageInner />
    </Suspense>
  );
}
