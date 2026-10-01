"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Info, X } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { EmptyState } from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";
import ToolBackLink from "@/components/ui/ToolBackLink";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { useVoices } from "@/hooks/useVoices";
import { useRouter } from "@/i18n/navigation";
import { DEMO_JOB, fetchDemo } from "../podcast/_api";
import PodcastStepper from "../podcast/_components/PodcastStepper";
import { demoSkript, demoVertonung, warte, type DemoView } from "../podcast/_demo";
import { closedForGood, isBusy, reachable } from "../podcast/_logic";
import { INITIAL_STATE, defaultPersons, reducer } from "../podcast/_reducer";
import CastStep from "../podcast/_steps/CastStep";
import ContentStep from "../podcast/_steps/ContentStep";
import DoneStep from "../podcast/_steps/DoneStep";
import ScriptStep from "../podcast/_steps/ScriptStep";
import VoicingStep from "../podcast/_steps/VoicingStep";
import { STEPS, type Line, type Person, type PodcastState, type Step } from "../podcast/_types";

const BEENDEN = "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-soft transition-colors hover:text-error focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb";
const keineAktion = () => {};

/** The real podcast steps on a prepared run, nothing that would need compute can be changed. */
function PodcastDemoLauf({ onNeu }: { onNeu: () => void }) {
  const tDemo = useTranslations("tools.podcastDemo");
  const router = useRouter();
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const llm = useFeatureProviders("/podcast/providers");
  const { loaded, providers } = useVoices();
  const [view, setView] = useState<DemoView | null>(null);
  const [fehlt, setFehlt] = useState(false);
  const [entwurf, setEntwurf] = useState<Line[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchDemo()
      .then((v) => {
        setView(v);
        const p = v.params;
        if (!p) return;
        const personen: Person[] = p.persons.map((x) => ({
          name: x.name, role: x.role as Person["role"], voiceId: x.voice_id, providerId: x.provider_id,
        }));
        dispatch({ type: "RESTORE", state: {
          language: p.language, instructions: p.instructions,
          length: p.length as PodcastState["length"], style: p.style as PodcastState["style"], speed: p.speed,
          count: Math.min(4, Math.max(1, personen.length)) as PodcastState["count"],
          persons: [...personen, ...defaultPersons().slice(personen.length)],
        } });
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

  // The script appears part by part like in a real run, then becomes the finished one.
  const schreiben = async () => {
    if (!view) return;
    const signal = neuerLauf();
    setEntwurf([]);
    dispatch({ type: "STARTING" });
    dispatch({ type: "STARTED", jobUuid: DEMO_JOB });
    try {
      for (const m of demoSkript(view.lines)) {
        dispatch({ type: "JOB", status: "running", progress: m.progress });
        setEntwurf(m.draft);
        await warte(m.ms, signal);
      }
      dispatch({ type: "LINES", lines: view.lines, voicedIds: [] });
      dispatch({ type: "JOB", status: "awaiting_user", progress: null });
    } catch { /* stopped by leaving the page */ }
  };

  const vertonen = async () => {
    if (!view) return;
    const signal = neuerLauf();
    dispatch({ type: "GO", step: "voicing" });
    try {
      for (const m of demoVertonung(view.lines)) {
        dispatch({ type: "JOB", status: "running", progress: m.progress });
        await warte(m.ms, signal);
      }
      dispatch({ type: "LINES", lines: view.lines, voicedIds: view.voiced });
      dispatch({ type: "JOB", status: "success", progress: null, seconds: view.seconds });
    } catch { /* stopped by the person or by leaving the page */ }
  };

  const abbrechen = () => {
    abortRef.current?.abort();
    dispatch({ type: "JOB", status: "awaiting_user", progress: null });
    dispatch({ type: "GO", step: "script" });
  };

  const beenden = () => {
    abortRef.current?.abort();
    router.push("/tools/podcast");
  };

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14">
        <ToolBackLink />
        {state.step !== "content" && (
          <>
            <div className="flex justify-end mb-3 sm:mb-8">
              <button type="button" onClick={beenden} className={BEENDEN}>
                <X size={14} aria-hidden="true" />
                {tDemo("beenden")}
              </button>
            </div>
            <p className="mb-8 flex items-start gap-2 rounded-lg bg-surface-dim px-3 py-2.5 text-sm text-foreground-soft">
              <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
              {tDemo("hinweis")}
            </p>
            <PodcastStepper step={state.step} canEnter={(i) => reachable(i, state)}
                            isClosedForGood={(i) => closedForGood(i, state)}
                            onStepClick={(i) => dispatch({ type: "GO", step: STEPS[i] as Step })} />
          </>
        )}

        {fehlt ? (
          <EmptyState text={tDemo("keinErgebnis")} />
        ) : !view ? (
          <Spinner className="justify-center py-20" />
        ) : (
          <>
            {state.step === "content" && (
              <ContentStep canUseModules={false} source={state.source} language={state.language}
                instructions={state.instructions} glossaryIds={state.glossaryIds}
                llmProviders={llm.providers} llmProviderId={llm.providerId} onLlmProvider={llm.setProviderId}
                onSource={keineAktion} onLanguage={keineAktion} onGlossaryIds={keineAktion} onInstructions={keineAktion}
                onNext={() => dispatch({ type: "GO", step: "cast" })}
                demo={{ workspace: view.workspace, files: view.files }} />
            )}
            {state.step === "cast" && (
              <CastStep count={state.count} persons={state.persons} length={state.length} style={state.style}
                voices={providers} voicesLoaded={loaded}
                onCount={keineAktion} onPerson={keineAktion} onLength={keineAktion} onStyle={keineAktion}
                onBack={state.jobUuid ? null : () => dispatch({ type: "GO", step: "content" })}
                onNext={state.jobUuid ? () => dispatch({ type: "GO", step: "script" }) : schreiben}
                hatAuftrag={state.jobUuid !== null} ohneKi={false} busy={false} error="" gesperrt />
            )}
            {state.step === "script" && (
              <ScriptStep lines={state.lines} draft={entwurf}
                draftParts={state.progress?.step === "script" && state.progress.total
                  ? { done: state.progress.part ?? 0, total: state.progress.total } : null}
                persons={state.persons} count={state.count} voicedIds={state.voicedIds} busy={isBusy(state)}
                error="" allDone={state.jobStatus === "success"} selfWritten={false} instructionUnmatched={false}
                regenAnchorIndex={null} regenAnchorText=""
                onUpdate={keineAktion} onSpeaker={keineAktion} onRegenAnchor={keineAktion} onOpenRegen={keineAktion}
                onDelete={keineAktion} onAdd={keineAktion}
                onBack={() => dispatch({ type: "GO", step: "cast" })}
                onVoice={vertonen} onToDone={() => dispatch({ type: "GO", step: "done" })} demo />
            )}
            {state.step === "voicing" && (
              <VoicingStep jobUuid={DEMO_JOB} lines={state.lines} persons={state.persons} voicedIds={state.voicedIds}
                jobStatus={state.jobStatus} progress={state.progress} error=""
                onResume={vertonen} onCancel={abbrechen}
                onBackToScript={() => dispatch({ type: "GO", step: "script" })}
                onWeiter={() => dispatch({ type: "GO", step: "done" })} demo />
            )}
            {state.step === "done" && (
              <DoneStep jobUuid={DEMO_JOB} lines={state.lines} persons={state.persons} count={state.count}
                voicedIds={state.voicedIds} jobStatus={state.jobStatus} progress={state.progress} seconds={state.seconds}
                onVoice={vertonen} onEditScript={() => dispatch({ type: "GO", step: "script" })} onReset={onNeu} />
            )}
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function PodcastDemoPage() {
  const [lauf, setLauf] = useState(0);
  return <PodcastDemoLauf key={lauf} onNeu={() => setLauf((n) => n + 1)} />;
}
