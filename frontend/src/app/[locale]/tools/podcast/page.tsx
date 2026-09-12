"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowCounterClockwise } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Spinner from "@/components/ui/Spinner";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { usePermissions } from "@/hooks/usePermissions";
import { useVoices } from "@/hooks/useVoices";
import PodcastStepper from "./_components/PodcastStepper";
import CastStep from "./_steps/CastStep";
import ContentStep from "./_steps/ContentStep";
import DoneStep from "./_steps/DoneStep";
import ScriptStep from "./_steps/ScriptStep";
import VoicingStep from "./_steps/VoicingStep";
import { cancelJob, fetchJob, fetchPodcast, rephraseLine, saveScript, startPodcast, startRender } from "./_api";
import { isBusy, reachable } from "./_logic";
import { INITIAL_STATE, defaultPersons, reducer } from "./_reducer";
import { clearStored, loadStored, saveStored } from "./_store";
import { STEPS, type Line, type Person, type PodcastState, type Step } from "./_types";

const ACTION = "px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap";
const POLL_MS = 2000;
const SAVE_MS = 800;

function PodcastPageInner() {
  const t = useTranslations("tools.podcast");
  const tCommon = useTranslations("common");
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const [hydrated, setHydrated] = useState(false);
  const { loaded, providers } = useVoices();
  const { permissions } = usePermissions();
  // The jobs list links straight to one podcast, that wins over the last one seen here.
  const ausListe = useSearchParams().get("job");
  const aenderung = useRef(0);
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
          count: Math.min(4, Math.max(1, personen.length)) as PodcastState["count"],
          // The saved cast first, the rest keeps its defaults so four cards stay fillable.
          persons: [...personen, ...defaultPersons().slice(personen.length)],
        },
      });
    }
    return view;
  }, []);

  // Whoever comes back finds their podcast, the server holds the truth.
  useEffect(() => {
    const stored = loadStored();
    if (!stored && !ausListe) {
      setHydrated(true);
      return;
    }
    const basis = stored ?? { ...INITIAL_STATE, jobUuid: null, step: "content" as const,
                              mode: "text" as const, text: "", moduleId: "", sourceIds: [] };
    const { step, mode, text, moduleId, sourceIds, ...rest } = basis as typeof basis & { jobUuid: string | null };
    const jobUuid = ausListe ?? basis.jobUuid;
    dispatch({
      type: "RESTORE",
      state: {
        instructions: rest.instructions,
        language: rest.language,
        count: rest.count,
        persons: rest.persons,
        length: rest.length,
        style: rest.style,
        jobUuid,
        step,
        maxReached: STEPS.indexOf(step),
        source: { mode, text, files: [], moduleId, sourceIds },
      },
    });
    if (!jobUuid) {
      setHydrated(true);
      return;
    }
    holeStand(jobUuid)
      .then(async (view) => {
        const meta = view.status === "success" ? await fetchJob(jobUuid).catch(() => null) : null;
        dispatch({ type: "JOB", status: view.status, progress: view.progress, error: view.error,
                   seconds: meta?.meta?.seconds ?? null });
        // A running job decides the step, a finished one leaves the choice.
        if (view.status === "pending" || view.status === "running") {
          dispatch({ type: "GO", step: view.progress?.step === "script" ? "script" : "voicing" });
        } else if (view.status === "awaiting_user") {
          dispatch({ type: "GO", step: "script" });
        } else if (view.status === "success") {
          dispatch({ type: "GO", step: step === "script" ? "script" : "done" });
        } else if (view.status === "failed") {
          dispatch({ type: "GO", step: view.lines.length ? "voicing" : "script" });
        }
      })
      .catch(() => clearStored())
      .finally(() => setHydrated(true));
  }, [holeStand, ausListe]);

  useEffect(() => {
    if (!hydrated) return;
    saveStored({
      jobUuid: state.jobUuid,
      step: state.step,
      mode: state.source.mode,
      text: state.source.text,
      moduleId: state.source.moduleId,
      sourceIds: state.source.sourceIds,
      instructions: state.instructions,
      language: state.language,
      count: state.count,
      persons: state.persons,
      length: state.length,
      style: state.style,
    });
  }, [state, hydrated]);

  // Empty voice fields get distinct voices once the list is there.
  useEffect(() => {
    if (!loaded) return;
    const alle = providers.flatMap((p) => p.voices.map((v) => ({ voiceId: v.voice_id, providerId: p.id })));
    if (!alle.length) return;
    state.persons.forEach((p, i) => {
      if (!p.voiceId || !p.providerId) dispatch({ type: "SET_PERSON", index: i, person: alle[i % alle.length] });
    });
  }, [loaded, providers, state.persons]);

  // While the job works, the page asks every two seconds, like every other tool.
  useEffect(() => {
    const uuid = state.jobUuid;
    if (!uuid || !(state.jobStatus === "pending" || state.jobStatus === "running")) return;
    let abgebrochen = false;
    const id = window.setInterval(async () => {
      try {
        const job = await fetchJob(uuid);
        if (abgebrochen) return;
        dispatch({ type: "JOB", status: job.status, progress: job.progress, error: job.error,
                   seconds: job.meta?.seconds ?? null });
        if (job.status !== "pending" && job.status !== "running") {
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

  const umformulieren = async (id: string) => {
    const uuid = stateRef.current.jobUuid;
    if (!uuid) return;
    try {
      const text = await rephraseLine(uuid, id);
      aendern({ type: "UPDATE_LINE", id, text });
    } catch (e) {
      dispatch({ type: "JOB", status: stateRef.current.jobStatus, progress: stateRef.current.progress,
                 error: e instanceof Error ? e.message : tCommon("unknownError") });
    }
  };

  const starten = async () => {
    dispatch({ type: "STARTING" });
    try {
      const uuid = await startPodcast(stateRef.current);
      dispatch({ type: "STARTED", jobUuid: uuid });
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

  const abbrechen = async () => {
    if (!state.jobUuid) return;
    await cancelJob(state.jobUuid);
    dispatch({ type: "JOB", status: "awaiting_user", progress: null, error: null });
    dispatch({ type: "GO", step: "script" });
    await holeStand(state.jobUuid);
    notifyJobsChanged();
  };

  const neu = () => {
    clearStored();
    dispatch({ type: "RESET" });
  };

  const gehe = (i: number) => dispatch({ type: "GO", step: STEPS[i] as Step });
  const begonnen = state.jobUuid !== null || state.step !== "content";

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14" data-tour="tool-podcast">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
          <h1 className="text-xl font-bold">{t("title")}</h1>
          {begonnen && (
            <button type="button" onClick={neu} className={ACTION}>
              <ArrowCounterClockwise size={14} weight="bold" />
              {t("newPodcast")}
            </button>
          )}
        </div>
        <p className="text-sm text-muted mb-8">{t("intro")}</p>

        {!hydrated ? (
          <Spinner className="justify-center py-20" />
        ) : (
          <>
            <PodcastStepper step={state.step} canEnter={(i) => reachable(i, state)} onStepClick={gehe} />

            {state.step === "content" && (
              <ContentStep
                canUseModules={permissions.allow_aia}
                source={state.source}
                language={state.language}
                instructions={state.instructions}
                onSource={(source) => dispatch({ type: "SET_SOURCE", source })}
                onLanguage={(language) => dispatch({ type: "SET_LANGUAGE", language })}
                onInstructions={(text) => dispatch({ type: "SET_INSTRUCTIONS", text })}
                onNext={() => dispatch({ type: "GO", step: "cast" })}
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
                onBack={() => dispatch({ type: "GO", step: "content" })}
                onNext={starten}
              />
            )}
            {state.step === "script" && (
              <ScriptStep
                lines={state.lines}
                persons={state.persons}
                count={state.count}
                voicedIds={state.voicedIds}
                busy={isBusy(state)}
                error={state.error}
                onUpdate={(id, text) => aendern({ type: "UPDATE_LINE", id, text })}
                onRephrase={umformulieren}
                onDelete={(id) => aendern({ type: "DELETE_LINE", id })}
                onAdd={() => aendern({ type: "ADD_LINE" })}
                onBack={state.jobUuid ? null : () => dispatch({ type: "GO", step: "cast" })}
                onVoice={vertonen}
                onToDone={() => dispatch({ type: "GO", step: "done" })}
                allDone={state.jobStatus === "success"}
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
                onCancel={abbrechen}
                onBackToScript={() => dispatch({ type: "GO", step: "script" })}
                onUpdate={(id, text) => aendern({ type: "UPDATE_LINE", id, text })}
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
                onUpdate={(id, text) => aendern({ type: "UPDATE_LINE", id, text })}
                onVoice={vertonen}
                onEditScript={() => dispatch({ type: "GO", step: "script" })}
                onReset={neu}
              />
            )}
          </>
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
