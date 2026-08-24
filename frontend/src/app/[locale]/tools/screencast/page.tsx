"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries } from "@/hooks/useGlossaries";


import Spinner from "@/components/ui/Spinner";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import { indexToStep, istErreichbar, stepToIndex, vorherErreichbar } from "@/components/screencast/steps";
import UploadStep from "./_steps/UploadStep";
import {
  TranslatingStep,
  GeneratingScriptsStep,
  RenderingStep,
  DoneStep,
  ErrorStep,
} from "./_steps/StatusSteps";
import UserPromptStep from "./_steps/UserPromptStep";
import TranslationReviewStep from "./_steps/TranslationReviewStep";
import ScriptReviewStep from "./_steps/ScriptReviewStep";
import TtsSettingsStep from "./_steps/TtsSettingsStep";
import Lightbox from "./_components/Lightbox";
import RenderVorschau from "./_components/RenderVorschau";
import RegenChatModal, { type RegenApplyMode } from "./_components/RegenChatModal";
import ExitConfirmModal from "./_components/ExitConfirmModal";
import { parseScriptJsonFile, checkHasActiveJob, checkJobValidity, checkJobFolderExists } from "./_utils";
import { flowReducer, INITIAL_FLOW_STATE } from "./_reducer";
import { useScreencastRenderFlow } from "./_hooks/useScreencastRenderFlow";
import { useScreencastTranslateFlow } from "./_hooks/useScreencastTranslateFlow";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { SCREENCAST_MAX_CHARS, SCREENCAST_TARGET_LANGUAGES } from "@/lib/constants";
import { wordCount } from "@/lib/text";
import { useFileDropzone } from "@/hooks/useFileDropzone";
import { useVoices } from "@/hooks/useVoices";
import { useScriptEditing, useScriptAutosave } from "@/hooks/useScriptEditing";
import { useScreencastResume, useSlideImageBackfill, useActiveJobCheck } from "@/hooks/useScreencastResume";
import { useLanguageConfig } from "@/hooks/useLanguageConfig";
import { useRenderResult } from "@/hooks/useRenderResult";
import { useFailedRender } from "@/hooks/useFailedRender";
import { useScriptInputMode } from "@/hooks/useScriptInputMode";
import { useRegenAnchor } from "@/hooks/useRegenAnchor";

const ACCEPTED_EXTENSIONS = [".pptx"];

const RENDER_SESSION_KEY = "kis_screencast_active_render";

function ScreencastPageInner() {
  const t = useTranslations("tools.screencast");
  const tCommon = useTranslations("common");
  const { mergeToApiJson } = useGlossaries();

  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const [fertigeFolien, setFertigeFolien] = useState<number[]>([]);
  // Beide Knöpfe oben löschen den Job samt Dateien. Vorher passierte das ohne
  // Rückfrage bei einem einzigen Klick, und beide taten exakt dasselbe.
  const [pendingExit, setPendingExit] = useState<"restart" | "cancel" | "render" | null>(null);
  const failedRender = useFailedRender();
  const { jobUuid: failedRenderJobUuid } = failedRender;
  const [ttsSettingsError, setTtsSettingsError] = useState("");

  // ── Job-Flow-State via Reducer ──
  const [flow, dispatch] = useReducer(flowReducer, INITIAL_FLOW_STATE);
  const { step, loading, errorMessage, slides, translateJobUuid, maxReachedIdx, correctedFileName, lightboxIndex } = flow;

  const {
    file,
    fileError,
    dragOver,
    selectFile: handleFileSelect,
    onDragOver: handleDragOver,
    onDragLeave: handleDragLeave,
    onDrop: handleDrop,
    reset: resetFile,
  } = useFileDropzone({ acceptedExtensions: ACCEPTED_EXTENSIONS });
  const [speed, setSpeed] = useState(0.9);
  const [slidePause, setSlidePause] = useState<number>(1.0);
  const [dpi, setDpi] = useState(96);
  const [subtitles, setSubtitles] = useState(false);
  const regen = useRegenAnchor();
  const { regeneratingSlide, anchorText: regenAnchorText, anchorSlide: regenAnchorSlide } = regen;


  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const [translationProviders, setTranslationProviders] = useState<{ id: number; name: string }[]>([]);
  const [translationProviderId, setTranslationProviderId] = useState<number | null>(null);
  const renderResult = useRenderResult();
  const { videoUrl, audioId, hasSubtitles, clear: clearRenderResult } = renderResult;

  const autosaveScripts = useScriptAutosave({ jobUuid: translateJobUuid });
  const {
    openAccordion,
    editingSlide,
    editBuffer,
    setEditBuffer,
    startEdit: startEditHook,
    cancelEdit,
    saveEdit,
    toggleAccordion,
    reset: resetScriptEditing,
  } = useScriptEditing({
    onSave: (index, newScript) => {
      dispatch({ type: "UPDATE_SLIDE_SCRIPT", index, script: newScript });
      const updated = slides.map((s, i) => (i === index ? { ...s, script: newScript } : s));
      autosaveScripts(updated.map((s) => s.script));
    },
  });
  const startEdit = (index: number) => startEditHook(index, slides[index]?.script ?? "");

  const voicesResult = useVoices();
  const {
    loaded: providersLoaded,
    providers,
    defaultProviderId,
    defaultVoiceId,
  } = voicesResult;
  const [voiceId, setVoiceId] = useState("");
  const [providerId, setProviderId] = useState<number>(0);
  useEffect(() => {
    if (defaultProviderId != null && providerId === 0) setProviderId(defaultProviderId);
  }, [defaultProviderId, providerId]);
  useEffect(() => {
    if (defaultVoiceId && !voiceId) setVoiceId(defaultVoiceId);
  }, [defaultVoiceId, voiceId]);
  const { languages, targetLang, setTargetLang } = useLanguageConfig(SCREENCAST_TARGET_LANGUAGES);
  const [skipTranslation, setSkipTranslation] = useState(false);
  const [hasActiveJob, setHasActiveJob] = useActiveJobCheck("screencast");

  useEffect(() => {
    fetch("/api/translate/config", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const provs: { id: number; name: string }[] = (data.providers ?? []).map(
          (p: { id: number; label: string }) => ({ id: p.id, name: p.label })
        );
        setTranslationProviders(provs);
        if (provs.length > 0) setTranslationProviderId(provs[0].id);
      })
      .catch(() => {});
  }, []);

  const scriptInput = useScriptInputMode();
  const {
    mode: scriptInputMode,
    setMode: setScriptInputMode,
    importedScripts,
    setImportedScripts,
    importError,
    setImportError,
    jsonDragOver,
    setJsonDragOver,
    jsonFileRef,
    resetImport,
  } = scriptInput;

  const fileRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);
  const isGeneratingScriptsRef = useRef(false);

  // ── Abort on unmount ──
  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
  }, []);


  // Die Vertonungs- und die Fertig-Seite brauchen den laufenden bzw. fertigen Job,
  // den holt ein Effekt weiter unten, sobald der Render-Hook steht.
  const [resumeIntoRender, setResumeIntoRender] = useState<{ uuid: string; step: "rendering" | "done" } | null>(null);
  // Das fertige Video wird erst geladen, solange bleibt der Fortsetzen-Spinner stehen.
  const [holeFertigesVideo, setHoleFertigesVideo] = useState(false);

  const { resumeLoading, resumeFailed } = useScreencastResume((payload) => {
    dispatch({ type: "RESUME", jobUuid: payload.jobUuid, slides: payload.slides, step: payload.step, stepIdx: payload.stepIdx });
    if (payload.step === "rendering" || payload.step === "done") {
      setResumeIntoRender({ uuid: payload.jobUuid, step: payload.step });
      if (payload.step === "done") setHoleFertigesVideo(true);
    }
  });
  const resumeBusy = resumeLoading || holeFertigesVideo;

  useSlideImageBackfill(translateJobUuid, slides, (images) => {
    dispatch({ type: "BACKFILL_IMAGES", images });
  });

  const checkBeforeSubmit = useCallback(async (): Promise<boolean> => {
    const result = await checkHasActiveJob("screencast");
    if (!result.ok) return true;
    setHasActiveJob(result.hasActive);
    return !result.hasActive;
  }, [setHasActiveJob]);

  const checkJobStillValid = useCallback(checkJobValidity, []);

  // ── Helpers ──

  const resetAll = useCallback((deleteJob = true) => {
    // Abort any in-flight request and optionally delete the current job (DB + MinIO)
    abortControllerRef.current?.abort();
    if (deleteJob) {
      const uuidToDelete = translateJobUuid || currentJobUuidRef.current;
      if (uuidToDelete) {
        fetch(`/api/jobs/${uuidToDelete}`, { method: "DELETE", credentials: "include" }).catch(() => {});
        notifyJobsChanged();
      }
    }
    currentJobUuidRef.current = null;

    dispatch({ type: "RESET" });
    resetFile();
    setSpeed(0.9);  // gleicher Startwert wie beim frischen Aufruf der Seite
    setSlidePause(1.0);
    setGlossaryIds(["", "", ""]);
    clearRenderResult();
    resetScriptEditing();
    failedRender.clear();
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setSkipTranslation(false);
    setTargetLang("EN-US");
    scriptInput.reset();
    if (fileRef.current) fileRef.current.value = "";
  }, [translateJobUuid]);

  const gotoIndex = useCallback((index: number) => {
    const target = indexToStep(index);
    if (target) dispatch({ type: "SET_STEP", step: target });
  }, []);

  const handleStepClick = useCallback((index: number) => {
    if (!istErreichbar(index, maxReachedIdx, skipTranslation, step)) return;
    gotoIndex(index);
  }, [gotoIndex, maxReachedIdx, skipTranslation, step]);

  /** Der Zuruecktritt einer Seite, oder null wenn davor nichts Betretbares liegt. */
  const zurueckVon = useCallback((index: number): (() => void) | null => {
    const ziel = vorherErreichbar(index, maxReachedIdx, skipTranslation, step);
    return ziel === null ? null : () => gotoIndex(ziel);
  }, [gotoIndex, maxReachedIdx, skipTranslation, step]);

  const goError = useCallback((msg: string) => {
    dispatch({ type: "GO_ERROR", message: msg });
  }, []);

  const checkJobFolder = useCallback(async (): Promise<boolean> => {
    if (!translateJobUuid) return true;
    const exists = await checkJobFolderExists(translateJobUuid);
    if (!exists) {
      goError(t("error.jobFolderMissing"));
      return false;
    }
    return true;
  }, [translateJobUuid, goError]);

  const {
    handleStartRender,
    handleRetryRender,
    newSignal,
    reconnectToRender,
    processRenderResultFromJob,
  } = useScreencastRenderFlow({
    translateJobUuid,
    slides,
    dispatch,
    targetLang,
    speed,
    slidePause,
    dpi,
    subtitles,
    voiceId,
    providerId,
    providers,
    failedRender,
    renderResult,
    checkBeforeSubmit,
    goError,
    setTtsSettingsError,
    setRenderProgressLabel,
    messages: {
      stuck: t("rendering.stuck"),
      queue: t("rendering.queue"),
      reconnected: t("rendering.reconnected"),
      renderError: t("error.renderError"),
      errorWithCode: (code: number) => t("error.errorWithCode", { code }),
      retryFailed: t("error.retryFailed"),
      tooManyJobs: t("error.tooManyJobs"),
      jobFailed: t("error.jobFailed"),
      unknownError: tCommon("unknownError"),
      previousRenderBusy: t("error.previousRenderBusy"),
      renderLabel: (p) => {
        switch (p.kind) {
          case "queue": return t("rendering.queue");
          case "translatePresentation": return t("rendering.translatePresentation");
          case "extractSlides": return t("rendering.extractSlides");
          case "scripts": return p.total != null ? t("rendering.scriptsWithCount", { n: p.total }) : t("rendering.scripts");
          case "images": return t("rendering.images");
          case "tts": return p.current != null && p.total != null
            ? t("rendering.ttsWithProgress", { current: p.current, total: p.total })
            : t("rendering.tts");
          case "video": return p.current != null && p.total != null
            ? t("rendering.videoWithProgress", { current: p.current, total: p.total })
            : t("rendering.video");
          case "concat": return t("rendering.concat");
          case "subtitles": return t("rendering.subtitles");
          default: return t("rendering.fallback");
        }
      },
    },
    setFertigeFolien,
    abortControllerRef,
    currentJobUuidRef,
  });

  // Sprung aus der Jobs-Liste auf die Vertonungs- oder die Fertig-Seite.
  useEffect(() => {
    if (!resumeIntoRender) return;
    const { uuid, step: ziel } = resumeIntoRender;
    setResumeIntoRender(null);
    if (ziel === "rendering") {
      reconnectToRender(uuid);
      return;
    }
    fetch(`/api/jobs/${uuid}`, { credentials: "include" })
      .then((r) => r.json())
      .then((job) => processRenderResultFromJob(job))
      .catch(() => goError(t("error.resumeFailed")))
      .finally(() => setHoleFertigesVideo(false));
  }, [resumeIntoRender, reconnectToRender, processRenderResultFromJob, goError, t]);

  const {
    handleUploadNext,
    handleDownloadTranslatedPptx,
    handleUploadCorrectedPptx,
    handleAcceptTranslation,
  } = useScreencastTranslateFlow({
    translateJobUuid,
    slides,
    dispatch,
    file,
    skipTranslation,
    targetLang,
    glossaryIds,
    translationProviderId,
    mergeToApiJson,
    checkBeforeSubmit,
    checkJobStillValid,
    checkJobFolder,
    goError,
    newSignal,
    messages: {
      unknownError: tCommon("unknownError"),
      errorWithCode: (code: number) => t("error.errorWithCode", { code }),
      uploadError: t("error.uploadError"),
      downloadFailed: t("error.downloadFailed"),
      jobInOtherTab: t("error.jobInOtherTab"),
      jobDeleted: t("error.jobDeleted"),
    },
    currentJobUuidRef,
    isGeneratingScriptsRef,
  });

  const handleJsonImport = useCallback(async (file: File) => {
    setImportError(null);
    const result = await parseScriptJsonFile(file);
    if ("error" in result && result.error) setImportError(result.error);
    else if (result.scripts) setImportedScripts(result.scripts);
  }, [setImportError, setImportedScripts]);


  // ── Accept scripts → TTS settings + fire-and-forget prerender + save ──
  const handleAcceptScripts = useCallback(() => {
    autosaveScripts(slides.map((s) => s.script), true); // save accepted_scripts.json
    dispatch({ type: "SET_STEP", step: "tts-settings" });
    if (translateJobUuid) {
      // dpi muss mitgeschickt werden, sonst passt das Vorgerenderte nicht zum Render.
      fetch("/api/screencast/prerender-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ translate_job_uuid: translateJobUuid, dpi }),
        credentials: "include",
      }).catch(() => {}); // fire and forget
    }
  }, [translateJobUuid, slides, autosaveScripts, dpi]);

  const abbrechenUndZurueck = useCallback(async () => {
    const uuid = currentJobUuidRef.current;
    currentJobUuidRef.current = null;
    abortControllerRef.current?.abort();
    if (uuid) {
      await fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
      notifyJobsChanged();
    }
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setFertigeFolien([]);
    setRenderProgressLabel("");
    dispatch({ type: "SET_STEP", step: "tts-settings" });
    dispatch({ type: "SET_LOADING", loading: false });
  }, []);

  // Den Dateinamen setzt das Backend im Kopf, deshalb reicht der schlichte Link.
  const handleDownload = () => {
    if (!audioId) return;
    const a = document.createElement("a");
    a.href = `/api/jobs/${audioId}/download`;
    a.download = "";
    a.click();
  };

  const openRegen = regen.open;
  const closeRegen = regen.close;

  const applyRegen = (index: number, mode: RegenApplyMode, content: string) => {
    const current = slides[index].script || "";
    let newScript = current;
    if (mode === "replace-all" || !regenAnchorText) {
      newScript = content;
    } else if (mode === "replace-selection") {
      newScript = current.replace(regenAnchorText, content);
    } else if (mode === "insert-before") {
      newScript = current.replace(regenAnchorText, content + " " + regenAnchorText);
    } else if (mode === "insert-after") {
      newScript = current.replace(regenAnchorText, regenAnchorText + " " + content);
    }
    dispatch({ type: "UPDATE_SLIDE_SCRIPT", index, script: newScript });
    const updated = slides.map((s, i) => i === index ? { ...s, script: newScript } : s);
    autosaveScripts(updated.map((s) => s.script));
    closeRegen();
  };

  // ── Back to script review (from tts-settings) ──
  const handleBackToScripts = () => {
    if (step === "rendering") return;
    dispatch({ type: "SET_STEP", step: "script-review" });
  };

  // ── Track max reached step ──
  useEffect(() => {
    dispatch({ type: "ADVANCE_REACHED", idx: stepToIndex(step) });
  }, [step]);

  // Zurueck auf Rendern kommt man nur, wenn das Video schon fertig ist.
  const rueckblick = step === "rendering" && videoUrl !== null;

  const showStepIndicator = step !== "upload" && step !== "error";

  const totalWords = slides.reduce(
    (sum, s) => sum + wordCount(s.script),
    0,
  );
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;


  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14">
        {/* Step indicator */}
        {showStepIndicator && (
          <>
            <div className="flex justify-end mb-8">
              <button
                onClick={() => setPendingExit("cancel")}
                className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-soft transition-colors hover:text-error focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
              >
                <Trash size={14} aria-hidden="true" />
                {t("exit.cancel")}
              </button>
            </div>
            <ScreencastStepper
              step={step}
              maxReachedIdx={maxReachedIdx}
              skipTranslation={skipTranslation}
              onStepClick={handleStepClick}
            />
          </>
        )}

        {/* ── Resume loading ── */}
        {resumeBusy && (
          <section className="animate-[fadeIn_0.2s_ease-out] text-center py-20" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-foreground-soft">{t("resuming")}</p>
          </section>
        )}

        {/* Fortsetzen ist fehlgeschlagen: sagen statt schweigend beim Upload landen */}
        {!resumeBusy && resumeFailed && step === "upload" && (
          <p className="mb-4 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
            {t("error.resumeFailed")}
          </p>
        )}

        {/* ── Step: Upload ── */}
        {!resumeBusy && step === "upload" && (
          <UploadStep
            onBack={zurueckVon(0)}
            hasActiveJob={hasActiveJob}
            file={file}
            fileError={fileError}
            dragOver={dragOver}
            skipTranslation={skipTranslation}
            targetLang={targetLang}
            languages={languages}
            glossaryIds={glossaryIds}
            fileRef={fileRef}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onFileSelect={handleFileSelect}
            onSkipTranslationChange={setSkipTranslation}
            onTargetLangChange={setTargetLang}
            onGlossaryIdsChange={setGlossaryIds}
            translationProviders={translationProviders}
            translationProviderId={translationProviderId}
            onTranslationProviderChange={setTranslationProviderId}
            onUploadNext={handleUploadNext}
          />
        )}

        {/* ── Step: Translating (loading) ── */}
        {!resumeBusy && step === "translating" && (
          <TranslatingStep
            skipTranslation={skipTranslation}
            onCancel={() => {
              const uuid = currentJobUuidRef.current;
              currentJobUuidRef.current = null;
              abortControllerRef.current?.abort();
              if (uuid) {
                fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {});
                notifyJobsChanged();
              }
              dispatch({ type: "SET_STEP", step: "upload" });
              dispatch({ type: "SET_LOADING", loading: false });
            }}
          />
        )}

        {/* ── Step: User Prompt ── */}
        {!resumeBusy && step === "user-prompt" && (
          <UserPromptStep
            onBack={zurueckVon(3)}
            scriptInputMode={scriptInputMode}
            importedScripts={importedScripts}
            importError={importError}
            jsonDragOver={jsonDragOver}
            jsonFileRef={jsonFileRef}
            loading={loading}
            onScriptInputModeChange={setScriptInputMode}
            onResetImport={resetImport}
            onJsonDragOverChange={setJsonDragOver}
            onJsonImport={handleJsonImport}
            onNext={() => {
              if (scriptInputMode === "manual") {
                dispatch({ type: "CLEAR_SCRIPTS" });
                dispatch({ type: "SET_STEP", step: "script-review" });
              } else if (scriptInputMode === "import") {
                if (!importedScripts) {
                  setImportError(t("selectJsonFirst"));
                  return;
                }
                dispatch({ type: "IMPORT_SCRIPTS", scripts: importedScripts });
                dispatch({ type: "SET_STEP", step: "script-review" });
              } else {
                handleAcceptTranslation();
              }
            }}
          />
        )}

        {/* ── Step: Translation Review ── */}
        {!resumeBusy && step === "translation-review" && (
          <TranslationReviewStep
            onBack={zurueckVon(2)}
            slides={slides}
            loading={loading}
            correctedFileName={correctedFileName}
            onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
            onDownloadTranslatedPptx={handleDownloadTranslatedPptx}
            onUploadCorrectedPptx={handleUploadCorrectedPptx}
            onAcceptAndNext={() => {
              dispatch({ type: "ADVANCE_REACHED", idx: 3 });
              dispatch({ type: "SET_STEP", step: "user-prompt" });
            }}
          />
        )}

        {/* ── Step: Generating Scripts (loading) ── */}
        {!resumeBusy && step === "generating-scripts" && (
          <GeneratingScriptsStep
            slideCount={slides.length}
            onCancel={() => {
              const uuid = currentJobUuidRef.current;
              currentJobUuidRef.current = null;
              abortControllerRef.current?.abort();
              if (uuid) {
                fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
                notifyJobsChanged();
              }
              dispatch({ type: "SET_STEP", step: "translation-review" });
              dispatch({ type: "SET_LOADING", loading: false });
            }}
          />
        )}

        {/* ── Step: Script Review ── */}
        {!resumeBusy && step === "script-review" && (
          <ScriptReviewStep
            onBack={zurueckVon(4)}
            slides={slides}
            openAccordion={openAccordion}
            editingSlide={editingSlide}
            editBuffer={editBuffer}
            regenAnchorSlide={regenAnchorSlide}
            regenAnchorText={regenAnchorText}
            onEditBufferChange={setEditBuffer}
            onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
            onAccordionToggle={toggleAccordion}
            onRegenAnchor={regen.setAnchor}
            onOpenRegen={openRegen}
            onStartEdit={startEdit}
            onCancelEdit={cancelEdit}
            onSaveEdit={saveEdit}
            onAcceptScripts={handleAcceptScripts}
          />
        )}

        {/* ── Step: TTS Settings ── */}
        {!resumeBusy && step === "tts-settings" && (
          <TtsSettingsStep
            onBack={zurueckVon(5)}
            providersLoaded={providersLoaded}
            providers={providers}
            providerId={providerId}
            targetLang={targetLang}
            languages={languages}
            onTargetLangChange={setTargetLang}
            voiceId={voiceId}
            speed={speed}
            slidePause={slidePause}
            dpi={dpi}
            subtitles={subtitles}
            slides={slides}
            totalWords={totalWords}
            totalChars={totalChars}
            scriptOverLimit={scriptOverLimit}
            maxChars={SCREENCAST_MAX_CHARS}
            ttsSettingsError={ttsSettingsError}
            onProviderIdChange={setProviderId}
            onVoiceIdChange={setVoiceId}
            onSpeedChange={setSpeed}
            onSlidePauseChange={setSlidePause}
            onDpiChange={setDpi}
            onSubtitlesChange={setSubtitles}
            onBackToScripts={handleBackToScripts}
            onStartRender={handleStartRender}
          />
        )}

        {/* ── Step: Rendering (loading) ── */}
        {!resumeBusy && step === "rendering" && (
          <RenderingStep
            renderProgressLabel={renderProgressLabel}
            rueckblick={rueckblick}
            vorschau={
              <RenderVorschau
                slides={slides}
                // Nach dem Lauf sind alle Folien vertont, der Ton kommt dann aus audio/.
                fertig={rueckblick ? slides.map((_, i) => i) : fertigeFolien}
                jobUuid={translateJobUuid}
                speed={speed}
                rueckblick={rueckblick}
              />
            }
            onCancel={() => setPendingExit("render")}
            onWeiter={() => dispatch({ type: "SET_STEP", step: "done" })}
          />
        )}

        {/* ── Step: Done ── */}
        {!resumeBusy && step === "done" && (
          <DoneStep
            videoUrl={videoUrl}
            audioId={audioId}
            hasSubtitles={hasSubtitles}
            onDownloadMp4={handleDownload}
            onReset={() => resetAll(false)}
          />
        )}

        {/* ── Error state ── */}
        {!resumeBusy && step === "error" && (
          <ErrorStep
            errorMessage={errorMessage}
            failedRenderJobUuid={failedRenderJobUuid}
            onRetry={handleRetryRender}
            onReset={() => resetAll()}
          />
        )}
        {pendingExit !== null && (
          <ExitConfirmModal
            mode={pendingExit}
            onCancel={() => setPendingExit(null)}
            onConfirm={async () => {
              const mode = pendingExit;
              setPendingExit(null);
              // Der Render-Abbruch loescht den Job nicht, er stoppt nur den Lauf.
              if (mode === "render") {
                await abbrechenUndZurueck();
                return;
              }
              resetAll(step !== "done");
              if (mode === "cancel") window.location.href = "/my-jobs";
            }}
          />
        )}

        {lightboxIndex !== null && (
          <Lightbox
            index={lightboxIndex}
            slides={slides}
            onClose={() => dispatch({ type: "SET_LIGHTBOX", index: null })}
            onIndexChange={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
          />
        )}


        {regeneratingSlide !== null && slides[regeneratingSlide] && (
          <RegenChatModal
            slideIndex={regeneratingSlide}
            slideExtractedText={slides[regeneratingSlide].extractedText}
            currentScript={slides[regeneratingSlide].script || ""}
            anchorText={regenAnchorText}
            targetLang={targetLang}
            onApply={(mode, content) => applyRegen(regeneratingSlide, mode, content)}
            onClose={closeRegen}
          />
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function ScreencastPage() {
  return (
    <Suspense>
      <ScreencastPageInner />
    </Suspense>
  );
}
