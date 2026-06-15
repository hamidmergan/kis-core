"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { parseDetail } from "@/lib/api";
import BackLink from "@/components/ui/BackLink";
import { SCREENCAST_MAX_CHARS } from "@/lib/constants";
import { wordCount } from "@/lib/text";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import { stepToIndex } from "@/components/screencast/steps";
import type {
  ScreencastStep,
  SlideData,
} from "@/types";
import type { ProviderWithVoices } from "@/hooks/useVoices";
import { UploadStep } from "./_steps/UploadStep";
import { TranslatingStep, GeneratingScriptsStep, RenderingStep, ErrorStep } from "./_steps/StatusSteps";
import { UserPromptStep } from "./_steps/UserPromptStep";
import { TranslationReviewStep } from "./_steps/TranslationReviewStep";
import { ScriptReviewStep } from "./_steps/ScriptReviewStep";
import { TtsSettingsStep } from "./_steps/TtsSettingsStep";
import { DoneStep } from "./_steps/DoneStep";
import RegenChatModal from "@/app/[locale]/tools/screencast/_components/RegenChatModal";
import { useDemoRegen } from "./_hooks/useDemoRegen";
import { useDemoScriptEditing } from "./_hooks/useDemoScriptEditing";

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

const RENDER_SESSION_KEY = "kis_screencast_demo_active_render";

function ScreencastDemoPageInner() {
  const t = useTranslations("tools.screencast");
  const tDemo = useTranslations("tools.screencastDemo");
  const tCommon = useTranslations("common");
  const [ttsSettingsError, setTtsSettingsError] = useState("");
  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const [step, setStep] = useState<ScreencastStep>("upload");
  const [speed, setSpeed] = useState(1.0);
  const [slidePause, setSlidePause] = useState<number>(0.5);
  const [dpi, setDpi] = useState(144);
  const [slides, setSlides] = useState<SlideData[]>([]);
  const { regeneratingSlide, openRegen, closeRegen } = useDemoRegen(slides, setSlides);
  const {
    openAccordion, editingSlide, editBuffer,
    setOpenAccordion, setEditBuffer, startEdit, saveEdit, cancelEdit, reset: resetScriptEditing,
  } = useDemoScriptEditing(slides, setSlides);
  const [translateJobUuid, setTranslateJobUuid] = useState("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  // TTS providers/voices — loaded from /api/tts/providers-with-voices
  const [providers, setProviders] = useState<ProviderWithVoices[]>([]);
  const [providerId, setProviderId] = useState<number>(0);
  const [voiceId, setVoiceId] = useState("");
  const [providersLoaded, setProvidersLoaded] = useState(false);

  const [audioId, setAudioId] = useState<string>("");
  const [maxReachedIdx, setMaxReachedIdx] = useState(0);
  const [scriptInputMode, setScriptInputMode] = useState<"generate" | "manual" | "import">("generate");
  const [importedScripts, setImportedScripts] = useState<string[] | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("/api/tts/providers-with-voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const list: ProviderWithVoices[] = data.providers ?? [];
        setProviders(list);
        if (list.length > 0) {
          setProviderId(list[0].id);
          if (list[0].voices.length > 0) setVoiceId(list[0].voices[0].voice_id);
        }
      })
      .catch(() => {})
      .finally(() => setProvidersLoaded(true));
  }, []);

  useEffect(() => { return () => { abortControllerRef.current?.abort(); }; }, []);

  const resetAll = useCallback(() => {
    abortControllerRef.current?.abort();
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setStep("upload");
    setSpeed(0.9);
    setSlidePause(0.5);
    setSlides([]);
    setTranslateJobUuid("");
    setDownloadBlob(null);
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoUrl(null);
    setErrorMessage("");
    setLoading(false);
    resetScriptEditing();
    setLightboxIndex(null);
    setAudioId("");
    setRenderProgressLabel("");
    setMaxReachedIdx(0);
    setScriptInputMode("generate");
    setImportedScripts(null);
    setImportError(null);
  }, [videoUrl]);

  const handleStepClick = useCallback((index: number) => {
    if (step === "rendering" || step === "generating-scripts") return;
    if (index > maxReachedIdx) return;
    const targets: Record<number, ScreencastStep | null> = {
      0: null, 1: null, 2: "translation-review", 3: "user-prompt",
      4: "script-review", 5: "tts-settings", 6: null, 7: "done",
    };
    const target = targets[index];
    if (!target) return;
    setStep(target);
  }, [maxReachedIdx, step]);

  const goError = useCallback((msg: string) => {
    setErrorMessage(msg);
    setStep("error");
    setLoading(false);
  }, []);

  const handleDemoStart = useCallback(async () => {
    setStep("translating");
    setLoading(true);
    try {
      const res = await fetch("/api/screencast-demo/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: tDemo("loadDemoError") }));
        throw new Error(parseDetail(err.detail, tDemo("errorWithCode", { code: res.status })));
      }
      const data: TranslateResponse = await res.json();
      setTranslateJobUuid(data.translate_job_uuid ?? "demo");
      setSlides(
        (data.slide_texts || []).map((text, i) => ({
          index: i,
          imageBase64: (data.slide_images || [])[i] || "",
          extractedText: text,
          script: "",
        })),
      );
      setLoading(false);
      setStep("translation-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : tCommon("unknownError"));
    }
  }, [goError, tDemo, tCommon]);

  const handleAcceptTranslation = useCallback(async () => {
    setStep("generating-scripts");
    setLoading(true);
    try {
      const res = await fetch("/api/screencast-demo/generate-scripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: tDemo("loadScriptsError") }));
        throw new Error(parseDetail(err.detail, tDemo("errorWithCode", { code: res.status })));
      }
      const data: GenerateScriptsResponse = await res.json();
      setSlides((prev) => prev.map((s, i) => ({ ...s, script: data.scripts[i] || "" })));
      setLoading(false);
      setStep("script-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : tCommon("unknownError"));
    }
  }, [goError, tDemo, tCommon]);

  const handleAcceptScripts = useCallback(() => { setStep("tts-settings"); }, []);

  const processRenderResponse = useCallback(async (response: Response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: t("error.renderError") }));
      throw new Error(parseDetail(err.detail, tDemo("errorWithCode", { code: response.status })));
    }
    const blob = await response.blob();
    const aId = response.headers.get("X-Audio-Id");
    if (aId) setAudioId(aId);
    setDownloadBlob(blob);
    const url = URL.createObjectURL(blob);
    setVideoUrl(url);
    setLoading(false);
    setStep("done");
  }, [t, tDemo]);

  const handleStartRender = useCallback(async () => {
    setTtsSettingsError("");
    setStep("rendering");
    setLoading(true);
    try {
      // Build voice label from loaded providers data
      const activeProvider = providers.find((p) => p.id === providerId);
      const activeVoice = activeProvider?.voices.find((v) => v.voice_id === voiceId);
      const LANGUAGE_FLAG: Record<string, string> = {
        de: "🇩🇪", en: "🇺🇸", fr: "🇫🇷", es: "🇪🇸",
        it: "🇮🇹", nl: "🇳🇱", pt: "🇵🇹", pl: "🇵🇱",
        tr: "🇹🇷", zh: "🇨🇳", ja: "🇯🇵", ko: "🇰🇷",
      };
      const voiceLabel = activeVoice
        ? `${LANGUAGE_FLAG[activeVoice.language] ?? ""} ${activeVoice.name}`.trim()
        : voiceId;

      const response = await fetch("/api/screencast-demo/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          translate_job_uuid: translateJobUuid || "demo",
          voice_id: voiceId, voice_label: voiceLabel,
          speed, slide_pause: slidePause, dpi, provider_id: providerId,
        }),
        credentials: "include",
      });
      await processRenderResponse(response);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : tCommon("unknownError"));
    }
  }, [voiceId, speed, slidePause, dpi, providerId, providers, translateJobUuid, goError, processRenderResponse, tCommon]);

  const handleJsonImport = useCallback((file: File) => {
    setImportError(null);
    if (!file.name.toLowerCase().endsWith(".json")) {
      setImportError(t("scriptImport.invalidExtension"));
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target?.result as string);
        if (!Array.isArray(parsed) || !parsed.every((x) => typeof x === "string")) {
          setImportError(t("scriptImport.mustBeArray"));
          return;
        }
        setImportedScripts(parsed);
      } catch {
        setImportError(t("scriptImport.parseError"));
      }
    };
    reader.readAsText(file);
  }, [t]);

  const handleDownload = () => {
    if (!downloadBlob) return;
    const url = URL.createObjectURL(downloadBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "screencast_demo.mp4";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleBackToScripts = () => { if (step === "rendering") return; setStep("script-review"); };

  useEffect(() => {
    const idx = stepToIndex(step);
    setMaxReachedIdx((prev) => Math.max(prev, idx));
  }, [step]);

  const showStepIndicator = step !== "upload" && step !== "error";
  const totalWords = slides.reduce((sum, s) => sum + wordCount(s.script), 0);
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink href="/tools/screencast" label={tDemo("backToScreencast")} />
        {showStepIndicator && (
          <>
            <ScreencastStepper
              step={step}
              maxReachedIdx={maxReachedIdx}
              skipTranslation={false}
              onStepClick={handleStepClick}
            />
            <div className="flex justify-between mb-6">
              <button
                onClick={() => resetAll()}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-muted-soft hover:text-kb rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {t("resetStart")}
              </button>
              <button
                onClick={() => resetAll()}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-error border-2 border-error-border hover:border-error rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                {t("cancelScreencast")}
              </button>
            </div>
          </>
        )}

        {step === "upload" && (
          <UploadStep onStart={handleDemoStart} />
        )}

        {step === "translating" && (
          <TranslatingStep
            onCancel={() => { abortControllerRef.current?.abort(); setStep("upload"); setLoading(false); }}
          />
        )}

        {step === "user-prompt" && (
          <UserPromptStep
            scriptInputMode={scriptInputMode}
            importedScripts={importedScripts}
            importError={importError}
            loading={loading}
            onScriptInputModeChange={setScriptInputMode}
            onClearImport={() => { setImportedScripts(null); setImportError(null); }}
            onJsonImport={handleJsonImport}
            onNext={() => {
              if (scriptInputMode === "manual") {
                setSlides((prev) => prev.map((s) => ({ ...s, script: "" })));
                setStep("script-review");
              } else if (scriptInputMode === "import") {
                if (!importedScripts) { setImportError(t("userPrompt.selectJsonFirst")); return; }
                setSlides((prev) => prev.map((s, i) => ({ ...s, script: importedScripts[i] ?? "" })));
                setStep("script-review");
              } else {
                handleAcceptTranslation();
              }
            }}
          />
        )}

        {step === "translation-review" && (
          <TranslationReviewStep
            slides={slides}
            loading={loading}
            lightboxIndex={lightboxIndex}
            onLightboxOpen={setLightboxIndex}
            onAcceptAndNext={() => { setMaxReachedIdx((v) => Math.max(v, 3)); setStep("user-prompt"); }}
          />
        )}

        {step === "generating-scripts" && (
          <GeneratingScriptsStep
            slideCount={slides.length}
            onCancel={() => { abortControllerRef.current?.abort(); setStep("translation-review"); setLoading(false); }}
          />
        )}

        {/* ── Step: Script Review ── */}
        {step === "script-review" && (
          <ScriptReviewStep
            slides={slides}
            openAccordion={openAccordion}
            editingSlide={editingSlide}
            editBuffer={editBuffer}
            regeneratingSlide={regeneratingSlide}
            onOpenAccordionChange={setOpenAccordion}
            onEditBufferChange={setEditBuffer}
            onStartEdit={startEdit}
            onCancelEdit={cancelEdit}
            onSaveEdit={saveEdit}
            onOpenRegen={openRegen}
            onAcceptScripts={handleAcceptScripts}
          />
        )}

        {/* ── Step: TTS Settings ── */}
        {step === "tts-settings" && (
          <TtsSettingsStep
            providersLoaded={providersLoaded}
            providers={providers}
            providerId={providerId}
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
            onProviderIdChange={setProviderId}
            onVoiceIdChange={setVoiceId}
            onSpeedChange={setSpeed}
            onSlidePauseChange={setSlidePause}
            onDpiChange={setDpi}
            onBackToScripts={handleBackToScripts}
            onStartRender={handleStartRender}
          />
        )}
        {/* ── Step: Rendering ── */}
        {step === "rendering" && (
          <RenderingStep
            renderProgressLabel={renderProgressLabel}
            onCancel={() => { abortControllerRef.current?.abort(); setRenderProgressLabel(""); setStep("tts-settings"); setLoading(false); }}
          />
        )}
        {/* ── Step: Done ── */}
        {step === "done" && (
          <DoneStep
            videoUrl={videoUrl}
            audioId={audioId}
            onDownloadMp4={handleDownload}
            onReset={() => resetAll()}
          />
        )}
        {step === "error" && (
          <ErrorStep errorMessage={errorMessage} onReset={() => resetAll()} />
        )}

        {regeneratingSlide !== null && slides[regeneratingSlide] && (
          <RegenChatModal
            slideIndex={regeneratingSlide}
            demo
            onClose={closeRegen}
          />
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function ScreencastDemoPage() {
  return (
    <Suspense>
      <ScreencastDemoPageInner />
    </Suspense>
  );
}
