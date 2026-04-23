"use client";

import { Suspense, useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import BackLink from "@/components/ui/BackLink";
import { wordCount } from "@/lib/text";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import type { SlideData } from "@/types";
import { UploadStep } from "./_steps/UploadStep";
import { TranslatingStep, GeneratingScriptsStep, RenderingStep, ErrorStep } from "./_steps/StatusSteps";
import { UserPromptStep } from "./_steps/UserPromptStep";
import { TranslationReviewStep } from "./_steps/TranslationReviewStep";
import { ScriptReviewStep } from "./_steps/ScriptReviewStep";
import { TtsSettingsStep } from "./_steps/TtsSettingsStep";
import { DoneStep } from "./_steps/DoneStep";
import { useDemoRegen } from "./_hooks/useDemoRegen";
import { useDemoScriptEditing } from "./_hooks/useDemoScriptEditing";
import { useDemoProviders } from "./_hooks/useDemoProviders";
import { useDemoFlow } from "./_hooks/useDemoFlow";

const SCREENCAST_MAX_CHARS = 100_000;


function ScreencastDemoPageInner() {
  const [fastMode, setFastMode] = useState(false);
  const [showSteps, setShowSteps] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [slides, setSlides] = useState<SlideData[]>([]);

  useEffect(() => {
    checkAuthStatus().then((status) => { setIsAdmin(!!status.is_admin); });
  }, []);

  const providers = useDemoProviders();
  const editing = useDemoScriptEditing(slides, setSlides);
  const regen = useDemoRegen(slides, setSlides);

  const flow = useDemoFlow({
    fastMode,
    ttsProvider: providers.ttsProvider,
    voiceId: providers.voiceId,
    kokoroVoices: providers.kokoroVoices,
    voices: providers.voices,
    resetScriptEditing: editing.reset,
    setTtsProvider: providers.setTtsProvider,
    kokoroEnabled: providers.kokoroEnabled,
    fishSpeechEnabled: providers.fishSpeechEnabled,
    elevenlabsEnabled: providers.elevenlabsEnabled,
    slides,
    setSlides,
  });

  const showStepIndicator = flow.step !== "upload" && flow.step !== "error";
  const totalWords = slides.reduce((sum, s) => sum + wordCount(s.script), 0);
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        {showStepIndicator && (
          <>
            <ScreencastStepper
              step={flow.step}
              maxReachedIdx={flow.maxReachedIdx}
              sourceLang="DE"
              onStepClick={flow.handleStepClick}
            />
            <div className="flex justify-between mb-6">
              <button
                onClick={() => flow.resetAll()}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Neu starten
              </button>
              <button
                onClick={() => flow.resetAll()}
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

        {flow.step === "upload" && (
          <UploadStep
            showSteps={showSteps}
            isAdmin={isAdmin}
            fastMode={fastMode}
            onShowStepsChange={setShowSteps}
            onFastModeChange={setFastMode}
            onStart={flow.handleDemoStart}
            onStartDirect={flow.handleDemoStartDirect}
          />
        )}

        {flow.step === "translating" && <TranslatingStep onCancel={flow.handleCancelTranslating} />}

        {flow.step === "user-prompt" && (
          <UserPromptStep
            scriptInputMode={flow.scriptInputMode}
            importedScripts={flow.importedScripts}
            importError={flow.importError}
            loading={flow.loading}
            onScriptInputModeChange={flow.setScriptInputMode}
            onClearImport={() => { flow.setImportedScripts(null); flow.setImportError(null); }}
            onJsonImport={flow.handleJsonImport}
            onNext={() => {
              if (flow.scriptInputMode === "manual") {
                setSlides((prev) => prev.map((s) => ({ ...s, script: "" })));
                flow.handleAcceptScripts();
              } else if (flow.scriptInputMode === "import") {
                if (!flow.importedScripts) {
                  flow.setImportError("Bitte zuerst eine JSON-Datei auswählen.");
                  return;
                }
                setSlides((prev) => prev.map((s, i) => ({ ...s, script: flow.importedScripts![i] ?? "" })));
                flow.handleAcceptScripts();
              } else {
                flow.handleAcceptTranslation();
              }
            }}
          />
        )}

        {flow.step === "translation-review" && (
          <TranslationReviewStep
            slides={slides}
            fastMode={fastMode}
            loading={flow.loading}
            lightboxIndex={null}
            onLightboxOpen={flow.setLightboxIndex}
            onAcceptAndNext={flow.handleAcceptTranslationAndAdvance}
          />
        )}

        {flow.step === "generating-scripts" && (
          <GeneratingScriptsStep slideCount={slides.length} onCancel={flow.handleCancelGeneratingScripts} />
        )}

        {flow.step === "script-review" && (
          <ScriptReviewStep
            slides={slides}
            openAccordion={editing.openAccordion}
            editingSlide={editing.editingSlide}
            editBuffer={editing.editBuffer}
            fastMode={fastMode}
            regeneratingSlide={regen.regeneratingSlide}
            regenPrompt={regen.regenPrompt}
            regenProposal={regen.regenProposal}
            regenLoading={regen.regenLoading}
            onOpenAccordionChange={editing.setOpenAccordion}
            onEditBufferChange={editing.setEditBuffer}
            onStartEdit={editing.startEdit}
            onCancelEdit={editing.cancelEdit}
            onSaveEdit={editing.saveEdit}
            onOpenRegen={regen.openRegen}
            onCloseRegen={regen.closeRegen}
            onRegenPromptChange={regen.setRegenPrompt}
            onRegenProposalChange={regen.setRegenProposal}
            onRunRegen={regen.runRegen}
            onApplyRegen={regen.applyRegen}
            onAcceptScripts={flow.handleAcceptScripts}
          />
        )}

        {flow.step === "tts-settings" && (
          <TtsSettingsStep
            providersLoaded={providers.providersLoaded}
            elevenlabsEnabled={providers.elevenlabsEnabled}
            fishSpeechEnabled={providers.fishSpeechEnabled}
            kokoroEnabled={providers.kokoroEnabled}
            mylabEnabled={providers.mylabEnabled}
            ttsProvider={providers.ttsProvider}
            voices={providers.voices}
            kokoroVoices={providers.kokoroVoices}
            mylabVoices={providers.mylabVoices}
            voiceId={providers.voiceId}
            speed={flow.speed}
            slidePause={flow.slidePause}
            dpi={flow.dpi}
            slides={slides}
            totalWords={totalWords}
            totalChars={totalChars}
            scriptOverLimit={scriptOverLimit}
            maxChars={SCREENCAST_MAX_CHARS}
            ttsSettingsError={flow.ttsSettingsError}
            onTtsProviderChange={providers.setTtsProvider}
            onVoiceIdChange={providers.setVoiceId}
            onSpeedChange={flow.setSpeed}
            onSlidePauseChange={flow.setSlidePause}
            onDpiChange={flow.setDpi}
            onBackToScripts={flow.handleBackToScripts}
            onStartRender={flow.handleStartRender}
          />
        )}

        {flow.step === "rendering" && (
          <RenderingStep renderProgressLabel={flow.renderProgressLabel} onCancel={flow.handleCancelRendering} />
        )}

        {flow.step === "done" && (
          <DoneStep videoUrl={flow.videoUrl} audioId={flow.audioId} onDownloadMp4={flow.handleDownload} onReset={flow.resetAll} />
        )}

        {flow.step === "error" && <ErrorStep errorMessage={flow.errorMessage} onReset={flow.resetAll} />}
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
