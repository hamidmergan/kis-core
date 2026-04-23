"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries } from "@/hooks/useGlossaries";


import BackLink from "@/components/ui/BackLink";
import { stepToIndex } from "@/components/screencast/steps";
import Lightbox from "./_components/Lightbox";
import RegenChatModal from "./_components/RegenChatModal";
import { ScreencastStepsView } from "./_components/ScreencastStepsView";
import { checkHasActiveJob, checkJobValidity } from "./_utils";
import { flowReducer, INITIAL_FLOW_STATE } from "./_reducer";
import { useScreencastRenderFlow } from "./_hooks/useScreencastRenderFlow";
import { useScreencastTranslateFlow } from "./_hooks/useScreencastTranslateFlow";
import { useScreencastPageActions } from "./_hooks/useScreencastPageActions";
import { wordCount } from "@/lib/text";
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

  const goError = useCallback((msg: string) => {
    dispatch({ type: "GO_ERROR", message: msg });
  }, []);

  const {
    resetAll,
    handleStepClick,
    checkJobFolder,
    handleAutoDownload,
    handleAutoZipDownload,
    handleJsonImport,
    handleAcceptScripts,
    handleDownload,
    applyRegen,
    handleBackToScripts,
    handleCancelTranslating,
    handleCancelGeneratingScripts,
    handleCancelRendering,
  } = useScreencastPageActions({
    step,
    slides,
    translateJobUuid,
    maxReachedIdx,
    mode,
    dispatch,
    resetFile,
    setSpeed,
    setSlidePause,
    setGlossaryIds,
    setSourceLang,
    setTargetLang,
    setTtsProvider,
    setImportError,
    setImportedScripts,
    kokoroEnabled,
    fishSpeechEnabled,
    elevenlabsEnabled,
    auto,
    failedRender,
    renderResult,
    scriptInput,
    resetScriptEditing,
    autosaveScripts,
    regenAnchorText,
    closeRegen: regen.close,
    file,
    downloadBlob,
    audioId,
    autoDownloadBlob,
    autoDownloadName,
    abortControllerRef,
    currentJobUuidRef,
    fileRef,
    goError,
    setRenderProgressLabel,
    setAutoState,
  });

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

  // ── Track max reached step ──
  useEffect(() => {
    dispatch({ type: "ADVANCE_REACHED", idx: stepToIndex(step) });
  }, [step]);

  const isAutoMode =
    mode === "auto" && step === "upload" && autoState !== "idle";

  const totalWords = slides.reduce(
    (sum, s) => sum + wordCount(s.script),
    0,
  );
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;


  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <ScreencastStepsView
          step={step}
          loading={loading}
          slides={slides}
          maxReachedIdx={maxReachedIdx}
          errorMessage={errorMessage}
          correctedFileName={correctedFileName}
          resumeLoading={resumeLoading}
          dispatch={dispatch}
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
          onZipDownload={handleAutoZipDownload}
          scriptInputMode={scriptInputMode}
          importedScripts={importedScripts}
          importError={importError}
          jsonDragOver={jsonDragOver}
          jsonFileRef={jsonFileRef}
          onScriptInputModeChange={setScriptInputMode}
          onResetImport={resetImport}
          onJsonDragOverChange={setJsonDragOver}
          onJsonImport={handleJsonImport}
          setImportError={setImportError}
          onAcceptTranslation={handleAcceptTranslation}
          onDownloadTranslatedPptx={handleDownloadTranslatedPptx}
          onUploadCorrectedPptx={handleUploadCorrectedPptx}
          openAccordion={openAccordion}
          editingSlide={editingSlide}
          editBuffer={editBuffer}
          regenAnchorSlide={regenAnchorSlide}
          regenAnchorText={regenAnchorText}
          onEditBufferChange={setEditBuffer}
          onAccordionToggle={toggleAccordion}
          onRegenAnchor={regen.setAnchor}
          onOpenRegen={regen.open}
          onStartEdit={startEdit}
          onCancelEdit={cancelEdit}
          onSaveEdit={saveEdit}
          onAcceptScripts={handleAcceptScripts}
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
          videoUrl={videoUrl}
          onDownloadMp4={handleDownload}
          onStepClick={handleStepClick}
          onReset={resetAll}
          onRetryRender={handleRetryRender}
          onCancelTranslating={handleCancelTranslating}
          onCancelGeneratingScripts={handleCancelGeneratingScripts}
          onCancelRendering={handleCancelRendering}
        />
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
            onClose={regen.close}
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
