"use client";

import { Info } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { useEffect, useReducer, useRef, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { EmptyState } from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";
import ToolBackLink from "@/components/ui/ToolBackLink";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { useRouter } from "@/i18n/navigation";
import * as api from "../praesentation/_api";
import PraesentationStepper from "../praesentation/_components/PraesentationStepper";
import { demoAblauf, warte, type DemoMoment, type DemoView } from "../praesentation/_demo";
import { closedForGood, isBusy, reachable } from "../praesentation/_logic";
import { INITIAL_STATE, reducer } from "../praesentation/_reducer";
import ContentStep from "../praesentation/_steps/ContentStep";
import DoneStep from "../praesentation/_steps/DoneStep";
import PreviewStep from "../praesentation/_steps/PreviewStep";
import { STEPS, type Language, type Step } from "../praesentation/_types";

// Milliseconds the finishing run takes before the deck is ready.
const BAU_MS = 1500;
const DEMO_BADGE = "text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent";
const DEMO_FARBE = { backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" };
const BEENDEN = `${DEMO_BADGE} hover:border-black transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb`;
const keineAktion = () => {};

/** The real presentation steps on a prepared run, nothing that would need compute can be changed. */
function PraesentationDemoLauf({ onNeu }: { onNeu: () => void }) {
  const t = useTranslations("tools.praesentation");
  const tDemo = useTranslations("tools.praesentationDemo");
  const router = useRouter();
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const llm = useFeatureProviders("/praesentation/providers");
  const [view, setView] = useState<DemoView | null>(null);
  const [fehlt, setFehlt] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    api.fetchDemo()
      .then((v) => {
        setView(v);
        const p = v.params;
        if (p) dispatch({ type: "RESTORE", state: { language: p.language as Language, instructions: p.instructions,
                          presenter: p.presenter ?? "", notes: p.notes, notesInclude: p.notes_include, templateId: p.template_id } });
      })
      .catch(() => setFehlt(true));
    return () => abortRef.current?.abort();
  }, []);

  const neuerLauf = () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    return ctrl.signal;
  };

  const zeige = (v: DemoView, m: DemoMoment) => {
    dispatch({ type: "VIEW", outline: m.stand.outline, slides: m.stand.slides, previews: m.stand.previews,
               missingImages: m.status === "awaiting_user" ? v.missing_images : [], images: m.stand.images,
               hasDeck: m.stand.hasDeck, templateFallback: false });
    dispatch({ type: "JOB", status: m.status, progress: m.progress });
  };

  const starten = async () => {
    if (!view) return;
    const signal = neuerLauf();
    dispatch({ type: "STARTING" });
    dispatch({ type: "STARTED", jobUuid: api.DEMO_JOB });
    try {
      for (const m of demoAblauf(view)) {
        zeige(view, m);
        await warte(m.ms, signal);
      }
    } catch { /* stopped by the person or by leaving the page */ }
  };

  const abbrechen = () => {
    abortRef.current?.abort();
    dispatch({ type: "BACK_TO_START" });
  };

  const fertigstellen = async () => {
    const signal = neuerLauf();
    dispatch({ type: "JOB", status: "pending", progress: { step: "bau", final: true } });
    dispatch({ type: "GO", step: "done" });
    try {
      await warte(BAU_MS, signal);
      dispatch({ type: "JOB", status: "success", progress: null });
    } catch { /* stopped by the person or by leaving the page */ }
  };

  const zurueckZurVorschau = () => {
    abortRef.current?.abort();
    dispatch({ type: "JOB", status: "awaiting_user", progress: null });
    dispatch({ type: "GO", step: "preview" });
  };

  const beenden = () => {
    abortRef.current?.abort();
    router.push("/tools/praesentation");
  };

  return (
    <ProtectedRoute>
      {/* Wide for the two columns of the first step, narrow for slides and the finished deck, like the tool itself. */}
      <div className={`${state.step === "content" ? "max-w-6xl" : "max-w-4xl"} mx-auto px-4 py-10 sm:py-14`}>
        <div className={state.step === "content" ? "" : "hidden sm:block"}><ToolBackLink /></div>
        {state.step === "content" ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-2xl font-bold">{t("title")}</h1>
              <button type="button" onClick={beenden} className={BEENDEN} style={DEMO_FARBE}>
                {tDemo("beenden")}
              </button>
            </div>
            <p className="text-sm text-muted mt-1 mb-4">{t("intro")}</p>
          </>
        ) : (
          <div className="flex justify-end mb-3 sm:mb-8">
            <button type="button" onClick={beenden} className={BEENDEN} style={DEMO_FARBE}>
              {tDemo("beenden")}
            </button>
          </div>
        )}
        <p className="mb-8 flex items-start gap-2 rounded-lg bg-surface-dim px-3 py-2.5 text-sm text-foreground-soft">
          <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
          {tDemo("hinweis")}
        </p>

        {fehlt ? (
          <EmptyState text={tDemo("keinErgebnis")} />
        ) : !view ? (
          <Spinner className="justify-center py-20" />
        ) : (
          <>
            {state.step !== "content" && (
              <PraesentationStepper step={state.step} canEnter={(i) => reachable(i, state)}
                                    isClosedForGood={(i) => closedForGood(i, state)}
                                    onStepClick={(i) => dispatch({ type: "GO", step: STEPS[i] as Step })} />
            )}
            {state.step === "content" && (
              <ContentStep canUseModules={false} source={state.source} language={state.language}
                notes={state.notes} instructions={state.instructions} imageStyle={state.imageStyle}
                presenter={state.presenter} templateId={state.templateId} hasActiveJob={null} error=""
                llmProviders={llm.providers} llmProviderId={llm.providerId} onLlmProvider={llm.setProviderId}
                onSource={keineAktion} onLanguage={keineAktion} onNotes={keineAktion} onInstructions={keineAktion}
                onImageStyle={keineAktion} onPresenter={keineAktion} onTemplate={keineAktion}
                onNext={starten} demo={{ workspace: view.workspace, files: view.files }} />
            )}
            {state.step === "preview" && (
              <PreviewStep jobUuid={api.DEMO_JOB} outline={state.outline} slides={state.slides} previews={state.previews}
                images={state.images} missingImages={state.missingImages} inArbeit={state.inArbeit} presenter={state.presenter}
                notesOn={state.notes} notesInclude={state.notesInclude} laeuft={isBusy(state)}
                jobStatus={state.jobStatus} progress={state.progress} error={state.error} hasOutline={!!state.outline}
                hasDeck={state.hasDeck} instructionUnmatched={false}
                onNotesInclude={(include) => dispatch({ type: "SET_NOTES_INCLUDE", include })}
                onSlide={keineAktion} onMove={keineAktion} onDelete={keineAktion} onInsertAfter={keineAktion}
                onRegenImage={keineAktion} onAnchor={keineAktion} onRestart={onNeu} onCancel={abbrechen}
                onResume={starten} onFinalize={fertigstellen} demo />
            )}
            {state.step === "done" && (
              <DoneStep jobUuid={api.DEMO_JOB} slides={state.slides} previews={state.previews}
                jobStatus={state.jobStatus} progress={state.progress} error={state.error}
                onResume={fertigstellen} onBackToPreview={zurueckZurVorschau} onNew={onNeu} onCancel={zurueckZurVorschau} demo />
            )}
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function PraesentationDemoPage() {
  const [lauf, setLauf] = useState(0);
  return <PraesentationDemoLauf key={lauf} onNeu={() => setLauf((n) => n + 1)} />;
}
