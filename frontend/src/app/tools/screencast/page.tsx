"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries } from "@/hooks/useGlossaries";


import BackLink from "@/components/ui/BackLink";
import Spinner from "@/components/ui/Spinner";
import type {
  ScreencastState,
  ScreencastStep,
  SlideData,
} from "@/types";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import { stepToIndex } from "@/components/screencast/steps";
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
import RegenChatModal, { type RegenApplyMode } from "./_components/RegenChatModal";
import { parseScriptJsonFile, triggerBlobDownload, triggerUrlDownload, checkHasActiveJob, checkJobValidity, checkJobFolderExists } from "./_utils";
import { flowReducer, INITIAL_FLOW_STATE } from "./_reducer";
import { useScreencastRenderFlow } from "./_hooks/useScreencastRenderFlow";
import { useScreencastTranslateFlow } from "./_hooks/useScreencastTranslateFlow";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { wordCount, estimateDuration } from "@/lib/text";
import { useFileDropzone } from "@/hooks/useFileDropzone";
import { useVoices } from "@/hooks/useVoices";
import { useScriptEditing, useScriptAutosave } from "@/hooks/useScriptEditing";
import { useScreencastResume, useSlideImageBackfill, useActiveJobCheck } from "@/hooks/useScreencastResume";
import { useLanguageConfig } from "@/hooks/useLanguageConfig";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import { useIsAdmin } from "@/hooks/useIsAdmin";
import { useRenderResult } from "@/hooks/useRenderResult";
import { useFailedRender } from "@/hooks/useFailedRender";
import { useAutoModeFlow } from "@/hooks/useAutoModeFlow";
import { useScriptInputMode } from "@/hooks/useScriptInputMode";
import { useRegenAnchor } from "@/hooks/useRegenAnchor";

const ACCEPTED_EXTENSIONS = [".pptx"];

interface TranslateResponse {
  slide_count: number;
  slide_texts: string[];
  slide_images: string[];
  translate_job_uuid?: string;
  user_prompt?: string;
}

interface GenerateScriptsResponse {
  scripts: string[];
}


const RENDER_SESSION_KEY = "kis_screencast_active_render";
const SCREENCAST_MAX_CHARS = 100_000;

function ScreencastPageInner() {
  const { mergeToApiJson } = useGlossaries();

  // ── Auto mode state ──
  const auto = useAutoModeFlow();
  const {
    state: autoState,
    setState: setAutoState,
    downloadBlob: autoDownloadBlob,
    downloadName: autoDownloadName,
    error: autoError,
    setError: setAutoError,
  } = auto;
  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const failedRender = useFailedRender();
  const { jobUuid: failedRenderJobUuid, isAuto: failedRenderIsAuto } = failedRender;
  const [ttsSettingsError, setTtsSettingsError] = useState("");

  // ── Job-Flow-State via Reducer ──
  const [flow, dispatch] = useReducer(flowReducer, INITIAL_FLOW_STATE);
  const { step, loading, errorMessage, slides, translateJobUuid, maxReachedIdx, correctedFileName, lightboxIndex, isResumedJob } = flow;

  const [mode, setMode] = useState<"auto" | "manual">("manual");
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
  const [speed, setSpeed] = useState(1.0);
  const [slidePause, setSlidePause] = useState<number>(0.5);
  const [dpi, setDpi] = useState(144);
  const regen = useRegenAnchor();
  const { regeneratingSlide, anchorText: regenAnchorText, anchorSlide: regenAnchorSlide } = regen;


  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const renderResult = useRenderResult();
  const { downloadBlob, videoUrl, audioId, audioCount, apply: applyRenderResult, clear: clearRenderResult } = renderResult;

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
    defaultProvider,
    defaultVoiceId,
    elevenlabs: voices,
    kokoro: kokoroVoices,
    mylab: mylabVoices,
    thorsten: thorstenVoices,
  } = voicesResult;
  const elevenlabsEnabled = providers.elevenlabs;
  const fishSpeechEnabled = providers.fish_speech;
  const kokoroEnabled = providers.kokoro;
  const mylabEnabled = providers.mylab;
  const thorstenEnabled = providers.thorsten;
  const [voiceId, setVoiceId] = useState("");
  const [ttsProvider, setTtsProvider] = useState<"elevenlabs" | "fish_speech" | "kokoro" | "mylab" | "thorsten">("kokoro");
  useEffect(() => {
    if (defaultProvider) setTtsProvider(defaultProvider);
  }, [defaultProvider]);
  useEffect(() => {
    if (defaultVoiceId && !voiceId) setVoiceId(defaultVoiceId);
  }, [defaultVoiceId, voiceId]);
  const { languages, sourceLang, setSourceLang, targetLang, setTargetLang } = useLanguageConfig();
  const [fastMode, setFastMode] = useState(false);
  const { isAdmin } = useIsAdmin();
  const { isToolEnabled } = useEnabledTools();
  const showDemoLink = isToolEnabled("screencast-demo");

  const [hasActiveJob, setHasActiveJob] = useActiveJobCheck("screencast");

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


  const { resumeLoading } = useScreencastResume((payload) => {
    dispatch({ type: "RESUME", jobUuid: payload.jobUuid, slides: payload.slides, step: payload.step, stepIdx: payload.stepIdx });
  });

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
    setSpeed(0.9);
    setSlidePause(0.5);
    setGlossaryIds(["", "", ""]);
    clearRenderResult();
    resetScriptEditing();
    auto.reset();
    failedRender.clear();
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setSourceLang("DE");
    setTargetLang("EN-US");
    scriptInput.reset();
    setTtsProvider(kokoroEnabled ? "kokoro" : fishSpeechEnabled ? "fish_speech" : elevenlabsEnabled ? "elevenlabs" : "kokoro");
    if (fileRef.current) fileRef.current.value = "";
  }, [translateJobUuid]);

  const handleStepClick = useCallback((index: number) => {
    if (step === "rendering" || step === "generating-scripts") return;
    if (index > maxReachedIdx) return;
    const targets: Record<number, ScreencastStep | null> = {
      0: null,
      1: null,
      2: "translation-review",
      3: "user-prompt",
      4: "script-review",
      5: "tts-settings",
      6: null,
      7: "done",
    };
    const target = targets[index];
    if (!target) return;
    dispatch({ type: "SET_STEP", step: target });
  }, [maxReachedIdx, step]);

  const goError = useCallback((msg: string) => {
    dispatch({ type: "GO_ERROR", message: msg });
  }, []);

  const checkJobFolder = useCallback(async (): Promise<boolean> => {
    if (!translateJobUuid) return true;
    const exists = await checkJobFolderExists(translateJobUuid);
    if (!exists) {
      goError("Job-Daten nicht mehr verfügbar — bitte neuen Screencast starten");
      return false;
    }
    return true;
  }, [translateJobUuid, goError]);

  const {
    onRenderProgress,
    handleAutoSubmit,
    handleStartRender,
    handleRetryRender,
    newSignal,
  } = useScreencastRenderFlow({
    translateJobUuid,
    slides,
    dispatch,
    file,
    speed,
    slidePause,
    dpi,
    voiceId,
    ttsProvider,
    kokoroVoices,
    voices,
    sourceLang,
    targetLang,
    glossaryIds,
    mergeToApiJson,
    auto,
    failedRender,
    renderResult,
    checkBeforeSubmit,
    goError,
    setTtsSettingsError,
    setRenderProgressLabel,
    abortControllerRef,
    currentJobUuidRef,
  });

  const handleAutoDownload = () => {
    if (!autoDownloadBlob) return;
    triggerBlobDownload(autoDownloadBlob, autoDownloadName);
  };

  const handleAutoZipDownload = useCallback(() => {
    if (!audioId) return;
    triggerUrlDownload(`/api/jobs/${audioId}/bundle`);
  }, [audioId]);

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
    mode,
    sourceLang,
    targetLang,
    fastMode,
    glossaryIds,
    mergeToApiJson,
    handleAutoSubmit,
    checkBeforeSubmit,
    checkJobStillValid,
    checkJobFolder,
    goError,
    newSignal,
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
      fetch("/api/screencast/prerender-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ translate_job_uuid: translateJobUuid }),
        credentials: "include",
      }).catch(() => {}); // fire and forget
    }
  }, [translateJobUuid, slides, autosaveScripts]);

  const handleDownload = () => {
    if (!downloadBlob) return;
    const stem = file?.name?.replace(/\.pptx$/i, "") || "screencast";
    triggerBlobDownload(downloadBlob, `${stem}_screencast_EN.mp4`);
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

  const isAutoMode =
    mode === "auto" && step === "upload" && autoState !== "idle";
  const showStepIndicator = step !== "upload" && step !== "error";

  const totalWords = slides.reduce(
    (sum, s) => sum + wordCount(s.script),
    0,
  );
  const totalDuration = estimateDuration(totalWords);
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;


  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        {/* Step indicator */}
        {showStepIndicator && (
          <>
            <ScreencastStepper
              step={step}
              maxReachedIdx={maxReachedIdx}
              sourceLang={sourceLang}
              onStepClick={handleStepClick}
            />
            <div className="flex justify-between mb-6">
              <button
                onClick={() => resetAll(step !== "done")}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Neu starten
              </button>
              <button
                onClick={() => resetAll(step !== "done")}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-red-400 hover:text-red-600 border border-red-200 hover:border-red-400 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                Screencast abbrechen
              </button>
            </div>
          </>
        )}

        {/* ── Resume loading ── */}
        {resumeLoading && (
          <section className="animate-[fadeIn_0.2s_ease-out] text-center py-16" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700">Screencast wird wiederhergestellt…</p>
          </section>
        )}

        {/* ── Step: Upload ── */}
        {!resumeLoading && step === "upload" && (
          <UploadStep
            showDemoLink={showDemoLink}
            hasActiveJob={hasActiveJob}
            file={file}
            fileError={fileError}
            dragOver={dragOver}
            autoState={autoState}
            mode={mode}
            isAdmin={isAdmin}
            fastMode={fastMode}
            sourceLang={sourceLang}
            targetLang={targetLang}
            languages={languages}
            glossaryIds={glossaryIds}
            isAutoMode={isAutoMode}
            autoDownloadName={autoDownloadName}
            autoError={autoError}
            renderProgressLabel={renderProgressLabel}
            failedRenderJobUuid={failedRenderJobUuid}
            audioId={audioId}
            fileRef={fileRef}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onFileSelect={handleFileSelect}
            onSourceLangChange={setSourceLang}
            onTargetLangChange={setTargetLang}
            onGlossaryIdsChange={setGlossaryIds}
            onModeChange={setMode}
            onFastModeChange={setFastMode}
            onUploadNext={handleUploadNext}
            onAutoDownload={handleAutoDownload}
            onReset={resetAll}
            onRetryRender={failedRenderJobUuid ? handleRetryRender : undefined}
            onZipDownload={handleAutoZipDownload}
          />
        )}

        {/* ── Step: Translating (loading) ── */}
        {!resumeLoading && step === "translating" && (
          <TranslatingStep
            sourceLang={sourceLang}
            targetLang={targetLang}
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
        {!resumeLoading && step === "user-prompt" && (
          <UserPromptStep
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
                  setImportError("Bitte zuerst eine JSON-Datei auswählen.");
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
        {!resumeLoading && step === "translation-review" && (
          <TranslationReviewStep
            slides={slides}
            fastMode={fastMode}
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
        {!resumeLoading && step === "generating-scripts" && (
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
        {!resumeLoading && step === "script-review" && (
          <ScriptReviewStep
            slides={slides}
            openAccordion={openAccordion}
            editingSlide={editingSlide}
            editBuffer={editBuffer}
            fastMode={fastMode}
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
        {!resumeLoading && step === "tts-settings" && (
          <TtsSettingsStep
            providersLoaded={providersLoaded}
            elevenlabsEnabled={elevenlabsEnabled}
            fishSpeechEnabled={fishSpeechEnabled}
            kokoroEnabled={kokoroEnabled}
            mylabEnabled={mylabEnabled}
            thorstenEnabled={thorstenEnabled}
            ttsProvider={ttsProvider}
            voices={voices}
            kokoroVoices={kokoroVoices}
            mylabVoices={mylabVoices}
            thorstenVoices={thorstenVoices}
            voiceId={voiceId}
            speed={speed}
            slidePause={slidePause}
            dpi={dpi}
            slides={slides}
            totalWords={totalWords}
            totalChars={totalChars}
            scriptOverLimit={scriptOverLimit}
            maxChars={SCREENCAST_MAX_CHARS}
            ttsSettingsError={ttsSettingsError}
            onTtsProviderChange={setTtsProvider}
            onVoiceIdChange={setVoiceId}
            onSpeedChange={setSpeed}
            onSlidePauseChange={setSlidePause}
            onDpiChange={setDpi}
            onBackToScripts={handleBackToScripts}
            onStartRender={handleStartRender}
          />
        )}

        {/* ── Step: Rendering (loading) ── */}
        {!resumeLoading && step === "rendering" && (
          <RenderingStep
            renderProgressLabel={renderProgressLabel}
            onCancel={async () => {
              const uuid = currentJobUuidRef.current;
              currentJobUuidRef.current = null;
              abortControllerRef.current?.abort();
              if (uuid) {
                await fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
                notifyJobsChanged();
              }
              setRenderProgressLabel("");
              setAutoState("idle");
              dispatch({ type: "SET_STEP", step: mode === "auto" ? "upload" : "tts-settings" });
              dispatch({ type: "SET_LOADING", loading: false });
            }}
          />
        )}

        {/* ── Step: Done ── */}
        {!resumeLoading && step === "done" && (
          <DoneStep
            videoUrl={videoUrl}
            audioId={audioId}
            onDownloadMp4={handleDownload}
            onReset={() => resetAll(false)}
          />
        )}

        {/* ── Error state ── */}
        {!resumeLoading && step === "error" && (
          <ErrorStep
            errorMessage={errorMessage}
            failedRenderJobUuid={failedRenderJobUuid}
            onRetry={handleRetryRender}
            onReset={() => resetAll()}
          />
        )}
        {!fastMode && lightboxIndex !== null && (
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
