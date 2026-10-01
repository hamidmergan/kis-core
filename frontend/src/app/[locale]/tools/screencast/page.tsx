"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Trash } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
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
import RenderVorschau from "./_components/RenderVorschau";
import ScreencastOverlays from "./_components/ScreencastOverlays";
import { applyRegen, type RegenApplyMode } from "@/components/regen/apply";
import { holeNotizen, parseScriptJsonFile, checkHasActiveJob, checkJobValidity, checkJobFolderExists, computeVoiceLabel, laufWaereUmsonst, stimmwechselOhneWirkung, sprachZuletztDerRueckfall, ausgeschlosseneFolien, sprachIdFuerLocale, type LaufStand } from "./_utils";
import { flowReducer, INITIAL_FLOW_STATE } from "./_reducer";
import { renderFlowMessages, translateFlowMessages } from "./_messages";
import { useScreencastRenderFlow } from "./_hooks/useScreencastRenderFlow";
import { useScreencastTranslateFlow } from "./_hooks/useScreencastTranslateFlow";
import { useSchritt6Stand } from "./_hooks/useSchritt6Stand";
import { useFolienAuswahl } from "./_hooks/useFolienAuswahl";
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
import { usePermissions } from "@/hooks/usePermissions";
import ZusatzMaterial from "./_components/ZusatzMaterial";
import { useZusatzMaterial } from "./_hooks/useZusatzMaterial";

const ACCEPTED_EXTENSIONS = [".pptx"];

const RENDER_SESSION_KEY = "kis_screencast_active_render";

function ScreencastPageInner() {
  const t = useTranslations("tools.screencast");
  const tCommon = useTranslations("common");
  const { mergeToApiJson } = useGlossaries();

  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const [fertigeFolien, setFertigeFolien] = useState<number[]>([]);
  const [nichtDabei, setNichtDabei] = useState<number[]>([]);
  // Both buttons delete the job with its files, now with a confirmation.
  const [pendingExit, setPendingExit] = useState<"restart" | "cancel" | "render" | null>(null);
  const failedRender = useFailedRender();
  const { jobUuid: failedRenderJobUuid, paused: renderAngehalten } = failedRender;
  const [ttsSettingsError, setTtsSettingsError] = useState("");
  const [uploadFehler, setUploadFehler] = useState<string>("");
  const [notizenFehler, setNotizenFehler] = useState("");

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
  // No tempo slider any more, a stretched voice echoes, so every video keeps the voice as it is.
  const speed = 1;
  const [slidePause, setSlidePause] = useState<number>(1.0);
  const [dpi, setDpi] = useState(96);
  const [subtitles, setSubtitles] = useState(false);
  const regen = useRegenAnchor();
  const { regeneratingSlide, anchorText: regenAnchorText, anchorSlide: regenAnchorSlide } = regen;


  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const [translationProviders, setTranslationProviders] = useState<{ id: number; name: string }[]>([]);
  const [translationProviderId, setTranslationProviderId] = useState<number | null>(null);
  const renderResult = useRenderResult();
  const { videoUrl, audioId, hasSubtitles, videoFolien, laufStempel, clear: clearRenderResult } = renderResult;

  // You can only get back to rendering when the video is already finished.
  const rueckblick = step === "rendering" && videoUrl !== null;

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
  const { geladen: standGeladen, einstellungen: gespeicherteEinstellungen, stand, hatTon, sprache: auftragsSprache } =
    useSchritt6Stand(translateJobUuid, step === "tts-settings");
  const auswahl = useFolienAuswahl({
    slides,
    stand,
    hatTon,
    gespeichert: gespeicherteEinstellungen
      ? { video_folien: gespeicherteEinstellungen.video_folien, neu_vertonen: gespeicherteEinstellungen.neu_vertonen }
      : null,
    bereit: standGeladen,
  });
  // After a reload the selection comes from the result instead of the progress.
  const ausgeschlossen = ausgeschlosseneFolien(slides.length, nichtDabei, videoFolien, auswahl.imScreencast);
  const zeigtNeu = hatTon.some(Boolean);
  // After a fallback run every slide is spoken anew, so no slide keeps an old voice.
  const stimmeGewechselt = !!stand && !sprachZuletztDerRueckfall(stand) &&
    (stand.voice_id !== voiceId || stand.provider_id !== providerId || stand.target_lang !== targetLang);
  const laufStand: LaufStand = {
    stand,
    hatVideo: videoUrl !== null,
    imScreencast: auswahl.imScreencast,
    neuVertonen: auswahl.neuVertonen,
    ohneTon: [...auswahl.ohneTon],
    geaendert: auswahl.geaendert,
    providerId,
    voiceId,
    targetLang,
    speed,
    slidePause,
    subtitles,
  };
  // A run without any change produces exactly the same video, that only costs time and quota.
  const laufUmsonst = laufWaereUmsonst(laufStand);
  // A new voice without a ticked slide would go unnoticed on the old video.
  const stimmwechselWirkungslos = stimmwechselOhneWirkung(laufStand);
  // Step 6 waits for the stored state, otherwise it overwrites a running edit.
  const schritt6Bereit = !translateJobUuid || standGeladen;

  // Whoever comes back tomorrow finds their state instead of the default.
  const eingestelltRef = useRef(false);
  useEffect(() => {
    const e = gespeicherteEinstellungen;
    if (!e || eingestelltRef.current) return;
    eingestelltRef.current = true;
    if (e.provider_id) setProviderId(e.provider_id);
    if (e.voice_id) setVoiceId(e.voice_id);
    if (e.target_lang) setTargetLang(e.target_lang);
    setSlidePause(e.slide_pause);
    setDpi(e.dpi);
    setSubtitles(e.subtitles);
  }, [gespeicherteEinstellungen, setTargetLang]);

  // Step 6 no longer asks for the language, a resumed job speaks the one chosen at the start.
  useEffect(() => {
    if (standGeladen && !gespeicherteEinstellungen?.target_lang && auftragsSprache) setTargetLang(auftragsSprache);
  }, [standGeladen, gespeicherteEinstellungen, auftragsSprache, setTargetLang]);

  // Saved on change, not only at render time.
  useEffect(() => {
    if (!translateJobUuid || !standGeladen || step !== "tts-settings") return;
    const zeit = setTimeout(() => {
      fetch(`/api/screencast/${translateJobUuid}/einstellungen`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_id: providerId,
          voice_id: voiceId,
          voice_label: computeVoiceLabel(providerId, voiceId, providers),
          target_lang: targetLang,
          speed,
          slide_pause: slidePause,
          dpi,
          subtitles,
          video_folien: auswahl.imScreencast,
          neu_vertonen: auswahl.neuVertonen,
        }),
        credentials: "include",
      }).catch(() => {});
    }, 600);
    return () => clearTimeout(zeit);
  }, [
    translateJobUuid, standGeladen, step, providerId, voiceId, providers, targetLang,
    speed, slidePause, dpi, subtitles, auswahl.imScreencast, auswahl.neuVertonen,
  ]);
  const [skipTranslation, setSkipTranslation] = useState(false);
  const locale = useLocale();

  // Without a translation the field proposes the interface language.
  const skipTranslationSetzen = useCallback((an: boolean) => {
    setSkipTranslation(an);
    if (!an) return;
    const id = sprachIdFuerLocale(locale, languages);
    if (id) setTargetLang(id);
  }, [languages, locale, setTargetLang]);
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

  const { permissions } = usePermissions();
  const zusatz = useZusatzMaterial(translateJobUuid, step === "user-prompt", tCommon("unknownError"));

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


  // Voicing and finished page need the job, an effect fetches it.
  const [resumeIntoRender, setResumeIntoRender] = useState<{ uuid: string; step: "rendering" | "done" } | null>(null);
  // The finished video is only loaded now, until then the resume spinner stays.
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
    setSlidePause(1.0);
    setGlossaryIds(["", "", ""]);
    setFertigeFolien([]);
    setNichtDabei([]);
    setUploadFehler("");
    setNotizenFehler("");
    clearRenderResult();
    resetScriptEditing();
    failedRender.clear();
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setSkipTranslation(false);
    setTargetLang("EN-US");
    scriptInput.reset();
    zusatz.reset();
    if (fileRef.current) fileRef.current.value = "";
  }, [translateJobUuid]);

  const gotoIndex = useCallback((index: number) => {
    const target = indexToStep(index);
    if (target) dispatch({ type: "SET_STEP", step: target });
  }, []);

  const handleStepClick = useCallback((index: number) => {
    if (!istErreichbar(index, maxReachedIdx, skipTranslation, step, videoUrl !== null)) return;
    gotoIndex(index);
  }, [gotoIndex, maxReachedIdx, skipTranslation, step, videoUrl]);

  /** The step back from a page, or null when nothing enterable lies before it. */
  const zurueckVon = useCallback((index: number): (() => void) | null => {
    const ziel = vorherErreichbar(index, maxReachedIdx, skipTranslation, step, videoUrl !== null);
    return ziel === null ? null : () => gotoIndex(ziel);
  }, [gotoIndex, maxReachedIdx, skipTranslation, step, videoUrl]);

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
    videoFolien: auswahl.imScreencast,
    neuVertonen: auswahl.neuVertonen,
    failedRender,
    renderResult,
    checkBeforeSubmit,
    goError,
    setTtsSettingsError,
    setRenderProgressLabel,
    messages: renderFlowMessages(t, tCommon),
    setFertigeFolien,
    setNichtDabei,
    abortControllerRef,
    currentJobUuidRef,
  });

  // Jump from the jobs list to the voicing or the finished page.
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
    setUploadFehler,
    newSignal,
    messages: translateFlowMessages(t, tCommon),
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
      // dpi has to be sent along, otherwise the pre-render does not match the render.
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
    setNichtDabei([]);
    setRenderProgressLabel("");
    dispatch({ type: "SET_STEP", step: "tts-settings" });
    dispatch({ type: "SET_LOADING", loading: false });
  }, []);

  // The backend sets the file name in the header, so a plain link is enough.
  const handleDownload = () => {
    if (!audioId) return;
    const a = document.createElement("a");
    a.href = `/api/jobs/${audioId}/download`;
    a.download = "";
    a.click();
  };

  const openRegen = regen.open;
  const closeRegen = regen.close;

  const handleApplyRegen = (index: number, mode: RegenApplyMode, content: string) => {
    const newScript = applyRegen(slides[index].script || "", regenAnchorText, mode, content);
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

  const showStepIndicator = step !== "upload" && step !== "error";

  // Only the chosen slides count, otherwise the start button stays locked after unticking.
  const gewaehlteFolien = new Set(auswahl.imScreencast);
  const totalWords = slides.reduce(
    (sum, s, i) => (gewaehlteFolien.has(i) ? sum + wordCount(s.script) : sum),
    0,
  );
  const totalChars = slides.reduce(
    (sum, s, i) => (gewaehlteFolien.has(i) ? sum + (s.script?.length ?? 0) : sum),
    0,
  );
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;
  // Changed but not yet ticked: the audio would otherwise stay the old one.
  const geaenderteOhneHaken = auswahl.geaendert.filter(
    (i) => auswahl.imScreencast.includes(i) && !auswahl.neuVertonen.includes(i),
  ).length;


  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14" data-tour="tool-screencast">
        <ToolBackLink />
        {/* Step indicator */}
        {showStepIndicator && (
          <>
            <div className="flex justify-end mb-3 sm:mb-8">
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
              hatErgebnis={videoUrl !== null}
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
            onSkipTranslationChange={skipTranslationSetzen}
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
            material={
              <ZusatzMaterial
                wahl={zusatz.wahl}
                onWahl={zusatz.waehlen}
                canUseModules={!!permissions.allow_aia}
                hinterlegt={zusatz.hinterlegt}
                onHinterlegtEntfernen={zusatz.hinterlegtEntfernen}
                fehler={zusatz.fehler}
                onBereit={zusatz.setBereit}
              />
            }
            nextBlocked={scriptInputMode === "generate" && (!zusatz.bereit || zusatz.laedt)}
            notizenFehler={notizenFehler}
            notizenUebersetzen={skipTranslation}
            onNext={async () => {
              if (scriptInputMode === "notes") {
                setNotizenFehler("");
                dispatch({ type: "SET_LOADING", loading: true });
                const notizen = await holeNotizen(translateJobUuid);
                dispatch({ type: "SET_LOADING", loading: false });
                if (!Array.isArray(notizen)) {
                  setNotizenFehler(notizen.fehler || tCommon("unknownError"));
                } else if (!notizen.some((n) => n.trim())) {
                  setNotizenFehler(t("userPrompt.notesEmpty"));
                } else {
                  dispatch({ type: "IMPORT_SCRIPTS", scripts: notizen });
                  dispatch({ type: "SET_STEP", step: "script-review" });
                }
                return;
              }
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
                if (!(await zusatz.abgleichen())) return;
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
            uploadFehler={uploadFehler}
            skipTranslation={skipTranslation}
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

        {/* ── Step: TTS Settings, wartet auf den gespeicherten Stand ── */}
        {!resumeBusy && step === "tts-settings" && !schritt6Bereit && (
          <section className="animate-[fadeIn_0.2s_ease-out] text-center py-20" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-foreground-soft">{t("resuming")}</p>
          </section>
        )}

        {/* ── Step: TTS Settings ── */}
        {!resumeBusy && step === "tts-settings" && schritt6Bereit && (
          <TtsSettingsStep
            onBack={zurueckVon(5)}
            providersLoaded={providersLoaded}
            providers={providers}
            providerId={providerId}
            voiceId={voiceId}
            slidePause={slidePause}
            subtitles={subtitles}
            slides={slides}
            totalWords={totalWords}
            totalChars={totalChars}
            scriptOverLimit={scriptOverLimit}
            maxChars={SCREENCAST_MAX_CHARS}
            ttsSettingsError={ttsSettingsError}
            stand={stand}
            imScreencast={auswahl.imScreencast}
            neuVertonen={auswahl.neuVertonen}
            ohneTon={auswahl.ohneTon}
            geaenderteOhneHaken={geaenderteOhneHaken}
            zeigtNeu={zeigtNeu}
            stimmeGewechselt={stimmeGewechselt}
            onUmschaltenScreencast={auswahl.umschaltenScreencast}
            onUmschaltenNeu={auswahl.umschaltenNeu}
            onAlleFolien={auswahl.setzeAlle}
            onKeineFolien={auswahl.setzeKeine}
            onGeaenderteFolien={auswahl.setzeGeaenderte}
            onProviderIdChange={setProviderId}
            onVoiceIdChange={setVoiceId}
            onSlidePauseChange={setSlidePause}
            onSubtitlesChange={setSubtitles}
            onBackToScripts={handleBackToScripts}
            onStartRender={handleStartRender}
            laufUmsonst={laufUmsonst}
            stimmwechselWirkungslos={stimmwechselWirkungslos}
            onZumVideo={() => dispatch({ type: "SET_STEP", step: "done" })}
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
                // Excluded slides stay out in the review too.
                fertig={rueckblick ? slides.map((_, i) => i).filter((i) => !ausgeschlossen.includes(i)) : fertigeFolien}
                jobUuid={translateJobUuid}
                speed={speed}
                rueckblick={rueckblick}
                nichtDabei={ausgeschlossen}
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
            laufStempel={laufStempel}
            onDownloadMp4={handleDownload}
            onReset={() => resetAll(false)}
            onNeuVertonen={() => dispatch({ type: "SET_STEP", step: "tts-settings" })}
          />
        )}

        {/* ── Error state ── */}
        {!resumeBusy && step === "error" && (
          <ErrorStep
            errorMessage={errorMessage}
            failedRenderJobUuid={failedRenderJobUuid}
            paused={renderAngehalten}
            onRetry={handleRetryRender}
            onReset={() => resetAll()}
          />
        )}
        <ScreencastOverlays
          slides={slides}
          jobUuid={translateJobUuid}
          targetLang={targetLang}
          glossaryJson={mergeToApiJson(glossaryIds) || ""}
          pendingExit={pendingExit}
          onExitCancel={() => setPendingExit(null)}
          onExitConfirm={async () => {
            const mode = pendingExit;
            setPendingExit(null);
            // Cancelling the render does not delete the job, it only stops the run.
            if (mode === "render") {
              await abbrechenUndZurueck();
              return;
            }
            resetAll(step !== "done");
            if (mode === "cancel") window.location.href = "/my-jobs";
          }}
          lightboxIndex={lightboxIndex}
          onLightboxIndexChange={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
          regeneratingSlide={regeneratingSlide}
          regenAnchorText={regenAnchorText}
          onRegenApply={handleApplyRegen}
          onRegenClose={closeRegen}
        />
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
