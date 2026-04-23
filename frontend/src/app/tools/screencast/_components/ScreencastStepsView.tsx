"use client";

import { type Dispatch, type SetStateAction, type RefObject, type DragEvent } from "react";
import Spinner from "@/components/ui/Spinner";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import type { ScreencastStep, ScreencastState, SlideData } from "@/types";
import type { ElevenLabsVoice, KokoroVoice, MylabVoice, ThorstenVoice, TtsProvider } from "@/hooks/useVoices";
import type { ScriptInputMode } from "@/hooks/useScriptInputMode";
import type { Language } from "@/hooks/useLanguageConfig";
import UploadStep from "../_steps/UploadStep";
import {
  TranslatingStep,
  GeneratingScriptsStep,
  RenderingStep,
  DoneStep,
  ErrorStep,
} from "../_steps/StatusSteps";
import UserPromptStep from "../_steps/UserPromptStep";
import TranslationReviewStep from "../_steps/TranslationReviewStep";
import ScriptReviewStep from "../_steps/ScriptReviewStep";
import TtsSettingsStep from "../_steps/TtsSettingsStep";
import type { FlowAction } from "../_reducer";

interface Props {
  // flow state
  step: ScreencastStep;
  loading: boolean;
  slides: SlideData[];
  maxReachedIdx: number;
  errorMessage: string;
  correctedFileName: string | null;
  resumeLoading: boolean;
  dispatch: Dispatch<FlowAction>;

  // upload step
  showDemoLink: boolean;
  hasActiveJob: boolean | null;
  file: File | null;
  fileError: string | null;
  dragOver: boolean;
  autoState: ScreencastState;
  mode: "auto" | "manual";
  isAdmin: boolean;
  fastMode: boolean;
  sourceLang: string;
  targetLang: string;
  languages: Language[];
  glossaryIds: string[];
  isAutoMode: boolean;
  autoDownloadName: string;
  autoError: string;
  renderProgressLabel: string;
  failedRenderJobUuid: string | null;
  audioId: string;
  fileRef: RefObject<HTMLInputElement | null>;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => void;
  onFileSelect: (f: File) => void;
  onSourceLangChange: (v: string) => void;
  onTargetLangChange: (v: string) => void;
  onGlossaryIdsChange: (v: string[]) => void;
  onModeChange: (v: "auto" | "manual") => void;
  onFastModeChange: (v: boolean) => void;
  onUploadNext: () => void;
  onAutoDownload: () => void;
  onZipDownload: () => void;

  // user-prompt step
  scriptInputMode: ScriptInputMode;
  importedScripts: string[] | null;
  importError: string | null;
  jsonDragOver: boolean;
  jsonFileRef: RefObject<HTMLInputElement | null>;
  onScriptInputModeChange: Dispatch<SetStateAction<ScriptInputMode>>;
  onResetImport: () => void;
  onJsonDragOverChange: Dispatch<SetStateAction<boolean>>;
  onJsonImport: (file: File) => Promise<void>;
  setImportError: Dispatch<SetStateAction<string | null>>;
  onAcceptTranslation: () => void;

  // translation review
  onDownloadTranslatedPptx: () => void;
  onUploadCorrectedPptx: (f: File) => void;

  // script review
  openAccordion: number;
  editingSlide: number | null;
  editBuffer: string;
  regenAnchorSlide: number | null;
  regenAnchorText: string;
  onEditBufferChange: Dispatch<SetStateAction<string>>;
  onAccordionToggle: (index: number) => void;
  onRegenAnchor: (slide: number | null, text: string) => void;
  onOpenRegen: (slide: number) => void;
  onStartEdit: (index: number) => void;
  onCancelEdit: () => void;
  onSaveEdit: (index: number) => void;
  onAcceptScripts: () => void;

  // tts settings
  providersLoaded: boolean;
  elevenlabsEnabled: boolean;
  fishSpeechEnabled: boolean;
  kokoroEnabled: boolean;
  mylabEnabled: boolean;
  thorstenEnabled: boolean;
  ttsProvider: TtsProvider;
  voices: ElevenLabsVoice[];
  kokoroVoices: KokoroVoice[];
  mylabVoices: MylabVoice[];
  thorstenVoices: ThorstenVoice[];
  voiceId: string;
  speed: number;
  slidePause: number;
  dpi: number;
  totalWords: number;
  totalChars: number;
  scriptOverLimit: boolean;
  maxChars: number;
  ttsSettingsError: string;
  onTtsProviderChange: (v: TtsProvider) => void;
  onVoiceIdChange: (v: string) => void;
  onSpeedChange: (v: number) => void;
  onSlidePauseChange: (v: number) => void;
  onDpiChange: (v: number) => void;
  onBackToScripts: () => void;
  onStartRender: () => void;

  // done / error
  videoUrl: string | null;
  onDownloadMp4: () => void;

  // common
  onStepClick: (index: number) => void;
  onReset: (deleteJob?: boolean) => void;
  onRetryRender: () => void;
  onCancelTranslating: () => void;
  onCancelGeneratingScripts: () => void;
  onCancelRendering: () => void;
}


export function ScreencastStepsView(props: Props) {
  const {
    step, loading, slides, maxReachedIdx, errorMessage, correctedFileName, resumeLoading, dispatch,
    sourceLang, targetLang, onStepClick, onReset,
    onCancelTranslating, onCancelGeneratingScripts, onCancelRendering,
  } = props;

  const showStepIndicator = step !== "upload" && step !== "error";

  return (
    <>
      {showStepIndicator && (
        <>
          <ScreencastStepper
            step={step}
            maxReachedIdx={maxReachedIdx}
            sourceLang={sourceLang}
            onStepClick={onStepClick}
          />
          <div className="flex justify-between mb-6">
            <button
              onClick={() => onReset(step !== "done")}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Neu starten
            </button>
            <button
              onClick={() => onReset(step !== "done")}
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

      {resumeLoading && (
        <section className="animate-[fadeIn_0.2s_ease-out] text-center py-16" role="status" aria-live="polite">
          <Spinner size="lg" className="justify-center mb-4" />
          <p className="text-sm text-gray-700">Screencast wird wiederhergestellt…</p>
        </section>
      )}

      {!resumeLoading && step === "upload" && (
        <UploadStep
          showDemoLink={props.showDemoLink}
          hasActiveJob={props.hasActiveJob}
          file={props.file}
          fileError={props.fileError}
          dragOver={props.dragOver}
          autoState={props.autoState}
          mode={props.mode}
          isAdmin={props.isAdmin}
          fastMode={props.fastMode}
          sourceLang={sourceLang}
          targetLang={targetLang}
          languages={props.languages}
          glossaryIds={props.glossaryIds}
          isAutoMode={props.isAutoMode}
          autoDownloadName={props.autoDownloadName}
          autoError={props.autoError}
          renderProgressLabel={props.renderProgressLabel}
          failedRenderJobUuid={props.failedRenderJobUuid}
          audioId={props.audioId}
          fileRef={props.fileRef}
          onDragOver={props.onDragOver}
          onDragLeave={props.onDragLeave}
          onDrop={props.onDrop}
          onFileSelect={props.onFileSelect}
          onSourceLangChange={props.onSourceLangChange}
          onTargetLangChange={props.onTargetLangChange}
          onGlossaryIdsChange={props.onGlossaryIdsChange}
          onModeChange={props.onModeChange}
          onFastModeChange={props.onFastModeChange}
          onUploadNext={props.onUploadNext}
          onAutoDownload={props.onAutoDownload}
          onReset={onReset}
          onRetryRender={props.failedRenderJobUuid ? props.onRetryRender : undefined}
          onZipDownload={props.onZipDownload}
        />
      )}

      {!resumeLoading && step === "translating" && (
        <TranslatingStep sourceLang={sourceLang} targetLang={targetLang} onCancel={onCancelTranslating} />
      )}

      {!resumeLoading && step === "user-prompt" && (
        <UserPromptStep
          scriptInputMode={props.scriptInputMode}
          importedScripts={props.importedScripts}
          importError={props.importError}
          jsonDragOver={props.jsonDragOver}
          jsonFileRef={props.jsonFileRef}
          loading={loading}
          onScriptInputModeChange={props.onScriptInputModeChange}
          onResetImport={props.onResetImport}
          onJsonDragOverChange={props.onJsonDragOverChange}
          onJsonImport={props.onJsonImport}
          onNext={() => {
            if (props.scriptInputMode === "manual") {
              dispatch({ type: "CLEAR_SCRIPTS" });
              dispatch({ type: "SET_STEP", step: "script-review" });
            } else if (props.scriptInputMode === "import") {
              if (!props.importedScripts) {
                props.setImportError("Bitte zuerst eine JSON-Datei auswählen.");
                return;
              }
              dispatch({ type: "IMPORT_SCRIPTS", scripts: props.importedScripts });
              dispatch({ type: "SET_STEP", step: "script-review" });
            } else {
              props.onAcceptTranslation();
            }
          }}
        />
      )}

      {!resumeLoading && step === "translation-review" && (
        <TranslationReviewStep
          slides={slides}
          fastMode={props.fastMode}
          loading={loading}
          correctedFileName={correctedFileName}
          onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
          onDownloadTranslatedPptx={props.onDownloadTranslatedPptx}
          onUploadCorrectedPptx={props.onUploadCorrectedPptx}
          onAcceptAndNext={() => {
            dispatch({ type: "ADVANCE_REACHED", idx: 3 });
            dispatch({ type: "SET_STEP", step: "user-prompt" });
          }}
        />
      )}

      {!resumeLoading && step === "generating-scripts" && (
        <GeneratingScriptsStep slideCount={slides.length} onCancel={onCancelGeneratingScripts} />
      )}

      {!resumeLoading && step === "script-review" && (
        <ScriptReviewStep
          slides={slides}
          openAccordion={props.openAccordion}
          editingSlide={props.editingSlide}
          editBuffer={props.editBuffer}
          fastMode={props.fastMode}
          regenAnchorSlide={props.regenAnchorSlide}
          regenAnchorText={props.regenAnchorText}
          onEditBufferChange={props.onEditBufferChange}
          onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
          onAccordionToggle={props.onAccordionToggle}
          onRegenAnchor={props.onRegenAnchor}
          onOpenRegen={props.onOpenRegen}
          onStartEdit={props.onStartEdit}
          onCancelEdit={props.onCancelEdit}
          onSaveEdit={props.onSaveEdit}
          onAcceptScripts={props.onAcceptScripts}
        />
      )}

      {!resumeLoading && step === "tts-settings" && (
        <TtsSettingsStep
          providersLoaded={props.providersLoaded}
          elevenlabsEnabled={props.elevenlabsEnabled}
          fishSpeechEnabled={props.fishSpeechEnabled}
          kokoroEnabled={props.kokoroEnabled}
          mylabEnabled={props.mylabEnabled}
          thorstenEnabled={props.thorstenEnabled}
          ttsProvider={props.ttsProvider}
          voices={props.voices}
          kokoroVoices={props.kokoroVoices}
          mylabVoices={props.mylabVoices}
          thorstenVoices={props.thorstenVoices}
          voiceId={props.voiceId}
          speed={props.speed}
          slidePause={props.slidePause}
          dpi={props.dpi}
          slides={slides}
          totalWords={props.totalWords}
          totalChars={props.totalChars}
          scriptOverLimit={props.scriptOverLimit}
          maxChars={props.maxChars}
          ttsSettingsError={props.ttsSettingsError}
          onTtsProviderChange={props.onTtsProviderChange}
          onVoiceIdChange={props.onVoiceIdChange}
          onSpeedChange={props.onSpeedChange}
          onSlidePauseChange={props.onSlidePauseChange}
          onDpiChange={props.onDpiChange}
          onBackToScripts={props.onBackToScripts}
          onStartRender={props.onStartRender}
        />
      )}

      {!resumeLoading && step === "rendering" && (
        <RenderingStep renderProgressLabel={props.renderProgressLabel} onCancel={onCancelRendering} />
      )}

      {!resumeLoading && step === "done" && (
        <DoneStep
          videoUrl={props.videoUrl}
          audioId={props.audioId}
          onDownloadMp4={props.onDownloadMp4}
          onReset={() => onReset(false)}
        />
      )}

      {!resumeLoading && step === "error" && (
        <ErrorStep
          errorMessage={errorMessage}
          failedRenderJobUuid={props.failedRenderJobUuid}
          onRetry={props.onRetryRender}
          onReset={() => onReset()}
        />
      )}
    </>
  );
}
