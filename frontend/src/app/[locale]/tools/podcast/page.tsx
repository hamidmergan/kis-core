"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Trash } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import Spinner from "@/components/ui/Spinner";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { usePermissions } from "@/hooks/usePermissions";
import { useRegenAnchor } from "@/hooks/useRegenAnchor";
import RegenChatModal, { type RegenTurn } from "@/components/regen/RegenChatModal";
import { applyRegen, type RegenApplyMode } from "@/components/regen/apply";
import { useVoices } from "@/hooks/useVoices";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import CastStep from "./_steps/CastStep";
import ContentStep from "./_steps/ContentStep";
import DoneStep from "./_steps/DoneStep";
import ScriptStep from "./_steps/ScriptStep";
import VoicingStep from "./_steps/VoicingStep";
import PodcastStepper from "./_components/PodcastStepper";
import BestaetigungModal from "./_components/BestaetigungModal";
import { cancelJob, demoAvailable, fetchJob, fetchPodcast, rephraseLine, savePodcastParams, saveScript, startPodcast, startRender } from "./_api";
import { LAEUFT, closedForGood, hatErgebnisse, isBusy, ohneKi, reachable } from "./_logic";
import { INITIAL_STATE, defaultPersons, reducer } from "./_reducer";
import { STEPS, type Line, type Person, type PodcastState, type Step } from "./_types";

// Same quiet discard link as the screencast tool.
const DISCARD = "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-soft transition-colors hover:text-error focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb";
const POLL_MS = 2000;
const SAVE_MS = 800;

function PodcastPageInner() {
  const t = useTranslations("tools.podcast");
  const tCommon = useTranslations("common");
  const tNachfrage = useTranslations("tools.podcast.nachfrage");
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  // The chat model that writes, picked in the first step and sent along with the start.
  const llm = useFeatureProviders("/podcast/providers");
  const [hydrated, setHydrated] = useState(false);
  const [besetzungLaeuft, setBesetzungLaeuft] = useState(false);
  const [demoDa, setDemoDa] = useState(false);
  // Both of these clicks throw work away, so neither happens without a question.
  const [nachfrage, setNachfrage] = useState<"abbrechen" | "neu" | null>(null);
  const { loaded, providers } = useVoices();
  const { permissions } = usePermissions();
  // Without it every visit starts fresh, only the jobs list links straight to one podcast.
  const ausListe = useSearchParams().get("job");
  const regen = useRegenAnchor();
  const aenderung = useRef(0);
  // The parts of the script already written, shown while the rest is still being written.
  const [entwurf, setEntwurf] = useState<Line[]>([]);
  const entwurfTeil = useRef(0);
  const stateRef = useRef(state);
  stateRef.current = state;

  /** Lines, cast and the voiced list always come from the server, never from a guess. */
  const holeStand = useCallback(async (jobUuid: string, uebernehmen = true) => {
    const view = await fetchPodcast(jobUuid);
    if (uebernehmen) dispatch({ type: "LINES", lines: view.lines, voicedIds: view.voiced });
    if (view.params) {
      const personen = view.params.persons.map((p) => ({
        name: p.name,
        role: p.role as Person["role"],
        voiceId: p.voice_id,
        providerId: p.provider_id,
      }));
      dispatch({
        type: "RESTORE",
        state: {
          language: view.params.language,
          instructions: view.params.instructions,
          length: view.params.length as PodcastState["length"],
          style: view.params.style as PodcastState["style"],
          speed: view.params.speed,
          count: Math.min(4, Math.max(1, personen.length)) as PodcastState["count"],
          selfWritten: view.params.self_written,
          instructionUnmatched: view.params.instruction_unmatched,
          // The saved cast first, the rest keeps its defaults so four cards stay fillable.
          persons: [...personen, ...defaultPersons().slice(personen.length)],
        },
      });
    }
    return view;
  }, []);

  // Every visit starts fresh, only the jobs list links straight to one podcast.
  useEffect(() => {
    if (!ausListe) {
      setHydrated(true);
      return;
    }
    dispatch({ type: "RESTORE", state: { jobUuid: ausListe } });
    holeStand(ausListe)
      .then(async (view) => {
        const meta = view.status === "success" ? await fetchJob(ausListe).catch(() => null) : null;
        dispatch({ type: "JOB", status: view.status, progress: view.progress, error: view.error,
                   seconds: meta?.meta?.seconds ?? null });
        if (view.status === "pending" || view.status === "running" || view.status === "waiting_retry") {
          dispatch({ type: "GO", step: view.progress?.step === "script" ? "script" : "voicing" });
        } else if (view.status === "awaiting_user") {
          dispatch({ type: "GO", step: "script" });
        } else if (view.status === "success") {
          dispatch({ type: "GO", step: "done" });
        } else if (view.status === "failed" || view.status === "paused") {
          dispatch({ type: "GO", step: view.lines.length ? "voicing" : "script" });
        }
      })
      .catch(() => {
        // Job expired, deleted or still running elsewhere, the page falls back to a fresh start.
      })
      .finally(() => setHydrated(true));
  }, [holeStand, ausListe]);

  useEffect(() => {
    demoAvailable().then(setDemoDa);
  }, []);

  // Another job starts with an empty draft.
  useEffect(() => {
    entwurfTeil.current = 0;
    setEntwurf([]);
  }, [state.jobUuid]);

  // While the job works, the page asks every two seconds, like every other tool.
  useEffect(() => {
    const uuid = state.jobUuid;
    if (!uuid || !LAEUFT.has(state.jobStatus)) return;
    let abgebrochen = false;
    const id = window.setInterval(async () => {
      try {
        const job = await fetchJob(uuid);
        if (abgebrochen) return;
        dispatch({ type: "JOB", status: job.status, progress: job.progress, error: job.error,
                   seconds: job.meta?.seconds ?? null });
        // A new part is done, its contributions can already be read.
        const teil = job.progress?.step === "script" ? job.progress.part ?? 0 : 0;
        if (teil > entwurfTeil.current) {
          entwurfTeil.current = teil;
          const view = await fetchPodcast(uuid);
          if (!abgebrochen) setEntwurf(view.draft ?? []);
        }
        if (!LAEUFT.has(job.status)) {
          await holeStand(uuid);
          notifyJobsChanged();
        }
      } catch {
        // A single failed poll means nothing, the next one follows.
      }
    }, POLL_MS);
    return () => {
      abgebrochen = true;
      window.clearInterval(id);
    };
  }, [state.jobUuid, state.jobStatus, holeStand]);

  // Every edit reaches the server on its own, nobody has to press save.
  const speichern = useCallback((lines: Line[]) => {
    const uuid = stateRef.current.jobUuid;
    if (!uuid) return;
    const marke = ++aenderung.current;
    window.setTimeout(async () => {
      if (marke !== aenderung.current) return;
      try {
        const frisch = await saveScript(uuid, lines);
        // Only adopt while nothing newer happened, the server hands out the ids.
        if (marke === aenderung.current) dispatch({ type: "LINES", lines: frisch });
      } catch {
        // The next edit tries again.
      }
    }, SAVE_MS);
  }, []);

  const aendern = (action: Parameters<typeof reducer>[1]) => {
    const naechster = reducer(stateRef.current, action);
    dispatch(action);
    speichern(naechster.lines);
  };

  /** The chat window at one contribution, the same one the screencast uses. */
  const regenLine = regen.regeneratingSlide !== null ? state.lines[regen.regeneratingSlide] : null;

  const umformulieren = async (messages: RegenTurn[]) => {
    const uuid = stateRef.current.jobUuid;
    if (!uuid || !regenLine) return "";
    return rephraseLine(uuid, regenLine.id, messages, regen.anchorText);
  };

  const uebernehmen = (mode: RegenApplyMode, content: string) => {
    if (!regenLine) return;
    aendern({ type: "UPDATE_LINE", id: regenLine.id, text: applyRegen(regenLine.text, regen.anchorText, mode, content) });
    regen.close();
  };

  const starten = async () => {
    dispatch({ type: "STARTING" });
    try {
      const uuid = await startPodcast(stateRef.current, llm.providerId);
      dispatch({ type: "STARTED", jobUuid: uuid });
      if (stateRef.current.source.mode === "blank") {
        const view = await holeStand(uuid);
        dispatch({ type: "JOB", status: view.status, progress: view.progress, error: view.error });
      }
      notifyJobsChanged();
    } catch (e) {
      dispatch({ type: "FAIL", error: e instanceof Error ? e.message : tCommon("unknownError") });
    }
  };

  const vertonen = async () => {
    const uuid = state.jobUuid;
    if (!uuid) return;
    dispatch({ type: "GO", step: "voicing" });
    try {
      await startRender(uuid);
      dispatch({ type: "JOB", status: "pending", progress: { step: "tts" }, error: null });
      notifyJobsChanged();
    } catch (e) {
      dispatch({ type: "FAIL", error: e instanceof Error ? e.message : tCommon("unknownError") });
    }
  };

  /** Back from the cast: without a job this starts one, with a job it only recasts. */
  const besetzungWeiter = async () => {
    const uuid = stateRef.current.jobUuid;
    if (!uuid) {
      await starten();
      return;
    }
    setBesetzungLaeuft(true);
    try {
      await savePodcastParams(uuid, stateRef.current);
      // The server decides which contributions still match their voice.
      await holeStand(uuid);
      dispatch({ type: "GO", step: "script" });
    } catch (e) {
      dispatch({ type: "JOB", status: stateRef.current.jobStatus, progress: stateRef.current.progress,
                 error: e instanceof Error ? e.message : tCommon("unknownError") });
    } finally {
      setBesetzungLaeuft(false);
    }
  };

  const abbrechen = async () => {
    setNachfrage(null);
    if (!state.jobUuid) return;
    await cancelJob(state.jobUuid);
    dispatch({ type: "JOB", status: "awaiting_user", progress: null, error: null });
    dispatch({ type: "GO", step: "script" });
    await holeStand(state.jobUuid);
    notifyJobsChanged();
  };

  const neu = () => {
    setNachfrage(null);
    dispatch({ type: "RESET" });
  };

  /** Without a script there is nothing to lose, the reset then goes straight through. */
  const neuGefragt = () => (hatErgebnisse(state) ? setNachfrage("neu") : neu());

  const gehe = (i: number) => dispatch({ type: "GO", step: STEPS[i] as Step });
  const begonnen = state.jobUuid !== null || state.step !== "content";
  const showStepIndicator = state.step !== "content";

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14" data-tour="tool-podcast">
        <ToolBackLink />

        {begonnen && (
          <div className="flex justify-end mb-3 sm:mb-8">
            <button type="button" onClick={neuGefragt} className={DISCARD}>
              <Trash size={14} aria-hidden="true" />
              {t("discardPodcast")}
            </button>
          </div>
        )}

        {!hydrated ? (
          <Spinner className="justify-center py-20" />
        ) : (
          <>
            {showStepIndicator && (
              <PodcastStepper
                step={state.step}
                canEnter={(i) => reachable(i, state)}
                isClosedForGood={(i) => closedForGood(i, state)}
                onStepClick={gehe}
              />
            )}

            {state.step === "content" && (
              <ContentStep
                canUseModules={permissions.allow_aia}
                source={state.source}
                language={state.language}
                instructions={state.instructions}
                llmProviders={llm.providers}
                llmProviderId={llm.providerId}
                onLlmProvider={llm.setProviderId}
                onSource={(source) => dispatch({ type: "SET_SOURCE", source })}
                onLanguage={(language) => dispatch({ type: "SET_LANGUAGE", language })}
                onInstructions={(text) => dispatch({ type: "SET_INSTRUCTIONS", text })}
                onNext={() => dispatch({ type: "GO", step: "cast" })}
                demoDa={demoDa}
              />
            )}
            {state.step === "cast" && (
              <CastStep
                count={state.count}
                persons={state.persons}
                length={state.length}
                style={state.style}
                voices={providers}
                voicesLoaded={loaded}
                onCount={(count) => dispatch({ type: "SET_COUNT", count })}
                onPerson={(index, person) => dispatch({ type: "SET_PERSON", index, person })}
                onLength={(length) => dispatch({ type: "SET_LENGTH", length })}
                onStyle={(style) => dispatch({ type: "SET_STYLE", style })}
                onBack={state.jobUuid ? null : () => dispatch({ type: "GO", step: "content" })}
                onNext={besetzungWeiter}
                hatAuftrag={state.jobUuid !== null}
                ohneKi={ohneKi(state)}
                busy={besetzungLaeuft}
                error={state.error}
              />
            )}
            {state.step === "script" && (
              <ScriptStep
                lines={state.lines}
                draft={entwurf}
                draftParts={state.progress?.step === "script" && state.progress.total
                  ? { done: state.progress.part ?? 0, total: state.progress.total } : null}
                persons={state.persons}
                count={state.count}
                voicedIds={state.voicedIds}
                busy={isBusy(state)}
                error={state.error}
                onUpdate={(id, text) => aendern({ type: "UPDATE_LINE", id, text })}
                onSpeaker={(id, speaker) => aendern({ type: "SET_SPEAKER", id, speaker })}
                onRegenAnchor={regen.setAnchor}
                onOpenRegen={regen.open}
                regenAnchorIndex={regen.anchorSlide}
                regenAnchorText={regen.anchorText}
                onDelete={(id) => aendern({ type: "DELETE_LINE", id })}
                onAdd={() => aendern({ type: "ADD_LINE" })}
                onBack={() => dispatch({ type: "GO", step: "cast" })}
                onVoice={vertonen}
                onToDone={() => dispatch({ type: "GO", step: "done" })}
                allDone={state.jobStatus === "success"}
                selfWritten={ohneKi(state)}
                instructionUnmatched={state.instructionUnmatched}
              />
            )}
            {state.step === "voicing" && (
              <VoicingStep
                jobUuid={state.jobUuid}
                lines={state.lines}
                persons={state.persons}
                voicedIds={state.voicedIds}
                jobStatus={state.jobStatus}
                progress={state.progress}
                error={state.error}
                onResume={vertonen}
                onCancel={() => setNachfrage("abbrechen")}
                onBackToScript={() => dispatch({ type: "GO", step: "script" })}
                onWeiter={() => dispatch({ type: "GO", step: "done" })}
              />
            )}
            {state.step === "done" && (
              <DoneStep
                jobUuid={state.jobUuid}
                lines={state.lines}
                persons={state.persons}
                count={state.count}
                voicedIds={state.voicedIds}
                jobStatus={state.jobStatus}
                progress={state.progress}
                seconds={state.seconds}
                onVoice={vertonen}
                onEditScript={() => dispatch({ type: "GO", step: "script" })}
                onReset={neuGefragt}
              />
            )}
          </>
        )}

        {regenLine && (
          <RegenChatModal
            index={regen.regeneratingSlide ?? 0}
            namespace="tools.podcast.regenChat"
            anchorText={regen.anchorText}
            onSend={umformulieren}
            onApply={uebernehmen}
            onClose={regen.close}
          />
        )}

        {nachfrage && (
          <BestaetigungModal
            title={nachfrage === "abbrechen" ? tNachfrage("abbrechenTitel") : tNachfrage("neuTitel")}
            body={nachfrage === "abbrechen" ? tNachfrage("abbrechenText") : tNachfrage("neuText")}
            dismissLabel={nachfrage === "abbrechen" ? tNachfrage("abbrechenWeiter") : tNachfrage("neuZurueck")}
            confirmLabel={nachfrage === "abbrechen" ? tNachfrage("abbrechenJa") : tNachfrage("neuJa")}
            onDismiss={() => setNachfrage(null)}
            onConfirm={nachfrage === "abbrechen" ? abbrechen : neu}
          />
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function PodcastPage() {
  return (
    <Suspense fallback={null}>
      <PodcastPageInner />
    </Suspense>
  );
}
