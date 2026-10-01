"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Info } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import { indexToStep, istErreichbar, startsAnew, stepToIndex, vorherErreichbar } from "@/components/screencast/steps";
import RegenChatModal from "@/components/regen/RegenChatModal";
import { useRouter } from "@/i18n/navigation";
import { parseDetail } from "@/lib/api";
import { SCREENCAST_MAX_CHARS, SCREENCAST_TARGET_LANGUAGES } from "@/lib/constants";
import { wordCount } from "@/lib/text";
import { useVoices } from "@/hooks/useVoices";
import { useLanguageConfig } from "@/hooks/useLanguageConfig";
import { useScriptEditing } from "@/hooks/useScriptEditing";
import { useScriptInputMode } from "@/hooks/useScriptInputMode";
import { useRegenAnchor } from "@/hooks/useRegenAnchor";
import UploadStep from "../screencast/_steps/UploadStep";
import { TranslatingStep, GeneratingScriptsStep, RenderingStep, DoneStep, ErrorStep } from "../screencast/_steps/StatusSteps";
import UserPromptStep from "../screencast/_steps/UserPromptStep";
import TranslationReviewStep from "../screencast/_steps/TranslationReviewStep";
import ScriptReviewStep from "../screencast/_steps/ScriptReviewStep";
import TtsSettingsStep from "../screencast/_steps/TtsSettingsStep";
import RenderVorschau from "../screencast/_components/RenderVorschau";
import Lightbox from "../screencast/_components/Lightbox";
import ZusatzMaterial, { KEIN_MATERIAL } from "../screencast/_components/ZusatzMaterial";
import { useFolienAuswahl } from "../screencast/_hooks/useFolienAuswahl";
import { flowReducer, INITIAL_FLOW_STATE } from "../screencast/_reducer";
import { sprachIdFuerLocale } from "../screencast/_utils";

const VIDEO_URL = "/api/screencast-demo/video";
const KEIN_TON: boolean[] = [];
// Waiting times of the simulated run in milliseconds.
const DAUER = { uebersetzen: 1200, skripte: 1500, folie: 220, schritt: 900 };
// The sample deck is German, carries its scripts in the speaker notes and was voiced by this voice.
const DEMO_SPRACHE = "DE";
const DEMO_STIMME = "thorsten";

function warte(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const zeit = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(zeit);
      reject(new DOMException("aborted", "AbortError"));
    });
  });
}

function herunterladen(href: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = "";
  a.click();
}

/** The real screencast steps on a prepared run, only own files are locked. */
function ScreencastDemoLauf({ onNeu }: { onNeu: () => void }) {
  const t = useTranslations("tools.screencast");
  const tDemo = useTranslations("tools.screencastDemo");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const locale = useLocale();

  const [flow, dispatch] = useReducer(flowReducer, INITIAL_FLOW_STATE);
  const { step, loading, errorMessage, slides, maxReachedIdx, lightboxIndex } = flow;

  const [skipTranslation, setSkipTranslation] = useState(true);
  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const [translationProviders, setTranslationProviders] = useState<{ id: number; name: string }[]>([]);
  const [translationProviderId, setTranslationProviderId] = useState<number | null>(null);
  const { languages, targetLang, setTargetLang } = useLanguageConfig(SCREENCAST_TARGET_LANGUAGES, DEMO_SPRACHE);

  const [slidePause, setSlidePause] = useState(1.0);
  const [subtitles, setSubtitles] = useState(false);
  const { loaded: providersLoaded, providers, defaultProviderId, defaultVoiceId } = useVoices();
  const [providerId, setProviderId] = useState(0);
  const [voiceId, setVoiceId] = useState("");
  // The voice of the prepared video comes first, the default only when it is not offered.
  useEffect(() => {
    if (!providersLoaded || providerId !== 0) return;
    const demo = providers.find((p) => p.voices.some((v) => v.voice_id === DEMO_STIMME));
    if (demo) {
      setProviderId(demo.id);
      setVoiceId(DEMO_STIMME);
    } else if (defaultProviderId != null) {
      setProviderId(defaultProviderId);
      setVoiceId(defaultVoiceId);
    }
  }, [providersLoaded, providers, providerId, defaultProviderId, defaultVoiceId]);

  const [fertigeFolien, setFertigeFolien] = useState<number[]>([]);
  const [renderLabel, setRenderLabel] = useState("");
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const scriptInput = useScriptInputMode("notes");
  const regen = useRegenAnchor();
  const editing = useScriptEditing({
    onSave: (index, script) => dispatch({ type: "UPDATE_SLIDE_SCRIPT", index, script }),
  });
  const auswahl = useFolienAuswahl({ slides, stand: null, hatTon: KEIN_TON, gespeichert: null, bereit: true });

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    fetch("/api/translate/config", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const provs: { id: number; name: string }[] = (data.providers ?? []).map(
          (p: { id: number; label: string }) => ({ id: p.id, name: p.label }),
        );
        setTranslationProviders(provs);
        if (provs.length > 0) setTranslationProviderId(provs[0].id);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    dispatch({ type: "ADVANCE_REACHED", idx: stepToIndex(step) });
  }, [step]);

  const neuerLauf = () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    return ctrl.signal;
  };

  const fehler = useCallback((err: unknown) => {
    if (err instanceof DOMException && err.name === "AbortError") return;
    dispatch({ type: "GO_ERROR", message: err instanceof Error ? err.message : tCommon("unknownError") });
  }, [tCommon]);

  const holeJson = async <T,>(pfad: string, signal: AbortSignal, fallback: string): Promise<T> => {
    const res = await fetch(pfad, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      credentials: "include",
      signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: fallback }));
      throw new Error(parseDetail(err.detail, tCommon("unknownError")));
    }
    return res.json();
  };

  const skipTranslationSetzen = useCallback((an: boolean) => {
    setSkipTranslation(an);
    if (!an) return;
    const id = sprachIdFuerLocale(locale, languages);
    if (id) setTargetLang(id);
  }, [languages, locale, setTargetLang]);

  const handleUploadNext = async () => {
    const signal = neuerLauf();
    dispatch({ type: "ENTER_STEP", step: "translating", loading: true });
    try {
      const [data] = await Promise.all([
        holeJson<{ slide_texts: string[]; slide_images: string[] }>(
          "/api/screencast-demo/translate", signal, tDemo("loadDemoError"),
        ),
        warte(DAUER.uebersetzen, signal),
      ]);
      dispatch({
        type: "SET_SLIDES",
        slides: data.slide_texts.map((text, index) => ({
          index,
          imageBase64: data.slide_images[index] ?? "",
          extractedText: text,
          script: "",
        })),
      });
      dispatch({ type: "ENTER_STEP", step: skipTranslation ? "user-prompt" : "translation-review", loading: false });
    } catch (err) {
      fehler(err);
    }
  };

  const vorbereiteteSkripte = async (mitWarten: boolean) => {
    const signal = neuerLauf();
    if (mitWarten) dispatch({ type: "ENTER_STEP", step: "generating-scripts", loading: true });
    try {
      const [data] = await Promise.all([
        holeJson<{ scripts: string[] }>("/api/screencast-demo/generate-scripts", signal, tDemo("loadScriptsError")),
        warte(mitWarten ? DAUER.skripte : 0, signal),
      ]);
      dispatch({ type: "IMPORT_SCRIPTS", scripts: data.scripts });
      dispatch({ type: "ENTER_STEP", step: "script-review", loading: false });
    } catch (err) {
      fehler(err);
    }
  };

  const handleStartRender = async () => {
    const signal = neuerLauf();
    const reihe = auswahl.imScreencast.filter((i) => slides[i]?.script.trim());
    setVideoUrl(null);
    setFertigeFolien([]);
    dispatch({ type: "ENTER_STEP", step: "rendering", loading: true });
    try {
      for (let k = 0; k < reihe.length; k++) {
        setRenderLabel(t("rendering.ttsWithProgress", { current: k + 1, total: reihe.length }));
        await warte(DAUER.folie, signal);
        setFertigeFolien(reihe.slice(0, k + 1));
      }
      setRenderLabel(t("rendering.video"));
      await warte(DAUER.schritt, signal);
      setRenderLabel(t("rendering.concat"));
      await warte(DAUER.schritt, signal);
      if (subtitles) {
        setRenderLabel(t("rendering.subtitles"));
        await warte(DAUER.schritt, signal);
      }
      setVideoUrl(VIDEO_URL);
      setRenderLabel("");
      dispatch({ type: "ENTER_STEP", step: "done", loading: false });
    } catch (err) {
      fehler(err);
    }
  };

  const zurueckZu = (ziel: "upload" | "translation-review" | "tts-settings") => {
    abortRef.current?.abort();
    setFertigeFolien([]);
    setRenderLabel("");
    dispatch({ type: "ENTER_STEP", step: ziel, loading: false });
  };

  const gotoIndex = useCallback((index: number) => {
    const target = indexToStep(index);
    if (target) dispatch({ type: "SET_STEP", step: target });
  }, []);

  const handleStepClick = useCallback((index: number) => {
    if (startsAnew(index, step)) return onNeu();
    if (!istErreichbar(index, maxReachedIdx, skipTranslation, step, videoUrl !== null)) return;
    gotoIndex(index);
  }, [gotoIndex, onNeu, maxReachedIdx, skipTranslation, step, videoUrl]);

  const zurueckVon = (index: number): (() => void) | null => {
    const ziel = vorherErreichbar(index, maxReachedIdx, skipTranslation, step, videoUrl !== null);
    return ziel === null ? null : () => gotoIndex(ziel);
  };

  const rueckblick = step === "rendering" && videoUrl !== null;
  const gewaehlt = new Set(auswahl.imScreencast);
  const nichtDabei = slides.map((_, i) => i).filter((i) => !gewaehlt.has(i));
  const totalWords = slides.reduce((sum, s, i) => (gewaehlt.has(i) ? sum + wordCount(s.script) : sum), 0);
  const totalChars = slides.reduce((sum, s, i) => (gewaehlt.has(i) ? sum + (s.script?.length ?? 0) : sum), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;
  const geaenderteOhneHaken = auswahl.geaendert.filter(
    (i) => gewaehlt.has(i) && !auswahl.neuVertonen.includes(i),
  ).length;
  const zeigtKopf = step !== "upload" && step !== "error";
  const beenden = () => {
    abortRef.current?.abort();
    router.push("/tools/screencast");
  };

  return (
    <ProtectedRoute>
      {/* Wide for the two columns of the upload, narrow for the steps that follow, like the tool itself. */}
      <div className={`${step === "upload" ? "max-w-6xl" : "max-w-4xl"} mx-auto px-4 py-10 sm:py-14`}>
        <div className={zeigtKopf ? "hidden sm:block" : ""}><ToolBackLink onRestart={zeigtKopf ? onNeu : undefined} /></div>
        {zeigtKopf && (
          <>
            <div className="flex justify-end mb-8">
              <button
                onClick={beenden}
                className="inline-flex items-center rounded px-3.5 py-1.5 text-xs font-semibold border-2 border-transparent hover:border-black transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
                style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
              >
                {tDemo("beenden")}
              </button>
            </div>
            <ScreencastStepper
              step={step}
              maxReachedIdx={maxReachedIdx}
              skipTranslation={skipTranslation}
              hatErgebnis={videoUrl !== null}
              onStepClick={handleStepClick}
            />
            <p className="mb-6 flex items-start gap-2 rounded-lg bg-surface-dim px-3 py-2.5 text-sm text-foreground-soft">
              <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
              {tDemo("hinweis")}
            </p>
          </>
        )}

        {step === "upload" && (
          <UploadStep
            onBack={null}
            hasActiveJob={false}
            file={null}
            fileError={null}
            dragOver={false}
            skipTranslation={skipTranslation}
            targetLang={targetLang}
            languages={languages}
            glossaryIds={glossaryIds}
            fileRef={{ current: null }}
            onDragOver={() => {}}
            onDragLeave={() => {}}
            onDrop={() => {}}
            onFileSelect={() => {}}
            onSkipTranslationChange={skipTranslationSetzen}
            onTargetLangChange={setTargetLang}
            onGlossaryIdsChange={setGlossaryIds}
            translationProviders={translationProviders}
            translationProviderId={translationProviderId}
            onTranslationProviderChange={setTranslationProviderId}
            onUploadNext={handleUploadNext}
            demoDatei={tDemo("dateiName")}
            onBeenden={beenden}
          />
        )}

        {step === "translating" && (
          <TranslatingStep skipTranslation={skipTranslation} onCancel={() => zurueckZu("upload")} ohneHintergrund />
        )}

        {step === "translation-review" && (
          <TranslationReviewStep
            onBack={zurueckVon(2)}
            slides={slides}
            loading={loading}
            correctedFileName={null}
            uploadFehler=""
            skipTranslation={skipTranslation}
            onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
            onDownloadTranslatedPptx={async () => {
              herunterladen("/api/screencast-demo/pptx");
              return true;
            }}
            onUploadCorrectedPptx={() => {}}
            onAcceptAndNext={() => {
              dispatch({ type: "ADVANCE_REACHED", idx: 3 });
              dispatch({ type: "SET_STEP", step: "user-prompt" });
            }}
            demo
          />
        )}

        {step === "user-prompt" && (
          <UserPromptStep
            onBack={zurueckVon(3)}
            scriptInputMode={scriptInput.mode}
            importedScripts={null}
            importError={null}
            jsonDragOver={false}
            jsonFileRef={scriptInput.jsonFileRef}
            loading={loading}
            onScriptInputModeChange={scriptInput.setMode}
            onResetImport={scriptInput.resetImport}
            onJsonDragOverChange={() => {}}
            onJsonImport={() => {}}
            material={
              <ZusatzMaterial
                wahl={KEIN_MATERIAL}
                onWahl={() => {}}
                canUseModules={false}
                hinterlegt={[]}
                onHinterlegtEntfernen={() => {}}
                fehler=""
                onBereit={() => {}}
                demo
              />
            }
            onNext={() => {
              if (scriptInput.mode === "manual") {
                dispatch({ type: "CLEAR_SCRIPTS" });
                dispatch({ type: "SET_STEP", step: "script-review" });
              } else {
                vorbereiteteSkripte(scriptInput.mode === "generate");
              }
            }}
            demo
          />
        )}

        {step === "generating-scripts" && (
          <GeneratingScriptsStep slideCount={slides.length} onCancel={() => zurueckZu("translation-review")} ohneHintergrund />
        )}

        {step === "script-review" && (
          <ScriptReviewStep
            onBack={zurueckVon(4)}
            slides={slides}
            openAccordion={editing.openAccordion}
            editingSlide={editing.editingSlide}
            editBuffer={editing.editBuffer}
            regenAnchorSlide={regen.anchorSlide}
            regenAnchorText={regen.anchorText}
            onEditBufferChange={editing.setEditBuffer}
            onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
            onAccordionToggle={editing.toggleAccordion}
            onRegenAnchor={regen.setAnchor}
            onOpenRegen={regen.open}
            onStartEdit={(i) => editing.startEdit(i, slides[i]?.script ?? "")}
            onCancelEdit={editing.cancelEdit}
            onSaveEdit={editing.saveEdit}
            onAcceptScripts={() => dispatch({ type: "SET_STEP", step: "tts-settings" })}
          />
        )}

        {step === "tts-settings" && (
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
            ttsSettingsError=""
            stand={null}
            imScreencast={auswahl.imScreencast}
            neuVertonen={auswahl.neuVertonen}
            ohneTon={auswahl.ohneTon}
            geaenderteOhneHaken={geaenderteOhneHaken}
            zeigtNeu={false}
            stimmeGewechselt={false}
            onUmschaltenScreencast={auswahl.umschaltenScreencast}
            onUmschaltenNeu={auswahl.umschaltenNeu}
            onAlleFolien={auswahl.setzeAlle}
            onKeineFolien={auswahl.setzeKeine}
            onGeaenderteFolien={auswahl.setzeGeaenderte}
            onProviderIdChange={setProviderId}
            onVoiceIdChange={setVoiceId}
            onSlidePauseChange={setSlidePause}
            onSubtitlesChange={setSubtitles}
            onBackToScripts={() => dispatch({ type: "SET_STEP", step: "script-review" })}
            onStartRender={handleStartRender}
            laufUmsonst={false}
            stimmwechselWirkungslos={false}
            onZumVideo={() => dispatch({ type: "SET_STEP", step: "done" })}
          />
        )}

        {step === "rendering" && (
          <RenderingStep
            renderProgressLabel={renderLabel}
            rueckblick={rueckblick}
            vorschau={
              <RenderVorschau
                slides={slides}
                fertig={rueckblick ? slides.map((_, i) => i).filter((i) => gewaehlt.has(i)) : fertigeFolien}
                jobUuid="demo"
                // The demo audio already carries the speed of the finished video.
                speed={1}
                rueckblick={rueckblick}
                nichtDabei={nichtDabei}
                tonUrl={(i) => `/api/screencast-demo/vorschau/${i}`}
              />
            }
            onCancel={() => zurueckZu("tts-settings")}
            onWeiter={() => dispatch({ type: "SET_STEP", step: "done" })}
            ohneHintergrund
          />
        )}

        {step === "done" && (
          <DoneStep
            videoUrl={videoUrl}
            audioId=""
            laufStempel=""
            onDownloadMp4={() => herunterladen(`${VIDEO_URL}?download=true`)}
            onReset={onNeu}
            onNeuVertonen={() => dispatch({ type: "SET_STEP", step: "tts-settings" })}
            zipUrl="/api/screencast-demo/bundle"
          />
        )}

        {step === "error" && (
          <ErrorStep errorMessage={errorMessage} failedRenderJobUuid={null} onRetry={() => {}} onReset={onNeu} />
        )}

        {lightboxIndex !== null && (
          <Lightbox
            index={lightboxIndex}
            slides={slides}
            onClose={() => dispatch({ type: "SET_LIGHTBOX", index: null })}
            onIndexChange={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
          />
        )}

        {regen.regeneratingSlide !== null && slides[regen.regeneratingSlide] && (
          <RegenChatModal
            index={regen.regeneratingSlide}
            anchorText={regen.anchorText}
            demo
            onSend={async () => ""}
            onClose={regen.close}
          />
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function ScreencastDemoPage() {
  const [lauf, setLauf] = useState(0);
  return (
    <Suspense>
      <ScreencastDemoLauf key={lauf} onNeu={() => setLauf((n) => n + 1)} />
    </Suspense>
  );
}
