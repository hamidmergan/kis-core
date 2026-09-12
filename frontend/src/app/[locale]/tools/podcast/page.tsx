"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowCounterClockwise } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Spinner from "@/components/ui/Spinner";
import { usePermissions } from "@/hooks/usePermissions";
import { useVoices, type ProviderWithVoices } from "@/hooks/useVoices";
import PodcastStepper from "./_components/PodcastStepper";
import CastStep from "./_steps/CastStep";
import ContentStep from "./_steps/ContentStep";
import DoneStep from "./_steps/DoneStep";
import ScriptStep from "./_steps/ScriptStep";
import VoicingStep from "./_steps/VoicingStep";
import { reachable } from "./_logic";
import { INITIAL_STATE, reducer } from "./_reducer";
import { sampleScript } from "./_samples";
import { clearState, loadState, saveState } from "./_store";
import { STEPS } from "./_types";

const ACTION = "px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap";
/** How long the mock takes per line and for the whole script. */
const TICK_MS = 700;
const GENERATE_MS = 1800;
/** Stand-in voices for a dev box without a speech provider. */
const FALLBACK_VOICES: ProviderWithVoices[] = [
  {
    id: 0,
    name: "Demo",
    voices: [
      { voice_id: "anna", name: "Anna", language: "de" },
      { voice_id: "ben", name: "Ben", language: "de" },
      { voice_id: "clara", name: "Clara", language: "de" },
      { voice_id: "david", name: "David", language: "de" },
    ],
  },
];

export default function PodcastPage() {
  const t = useTranslations("tools.podcast");
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const [hydrated, setHydrated] = useState(false);
  const { loaded, providers } = useVoices();
  const { permissions } = usePermissions();
  const voices = providers.length ? providers : FALLBACK_VOICES;
  const stateRef = useRef(state);
  stateRef.current = state;

  // Whoever comes back finds their state, the mockup keeps it in the browser.
  useEffect(() => {
    const saved = loadState();
    if (saved) dispatch({ type: "LOAD", state: saved });
    setHydrated(true);
  }, []);
  useEffect(() => {
    if (hydrated) saveState(state);
  }, [state, hydrated]);

  // Empty voice fields get distinct voices once the list is there.
  useEffect(() => {
    if (!loaded) return;
    const all = voices.flatMap((p) => p.voices);
    if (!all.length) return;
    state.persons.forEach((p, i) => {
      if (!p.voiceId) dispatch({ type: "SET_PERSON", index: i, person: { voiceId: all[i % all.length].voice_id } });
    });
  }, [loaded, voices, state.persons]);

  // The model is a timer here, the real build waits for the job.
  useEffect(() => {
    if (!state.generating) return;
    const id = window.setTimeout(() => {
      const s = stateRef.current;
      dispatch({ type: "GENERATE_DONE", lines: sampleScript(s.language, s.persons.slice(0, s.count)) });
    }, GENERATE_MS);
    return () => window.clearTimeout(id);
  }, [state.generating]);

  // A running voicing keeps ticking, also after a reload of the page.
  useEffect(() => {
    if (state.run.status !== "running") return;
    const id = window.setInterval(() => dispatch({ type: "TICK" }), TICK_MS);
    return () => window.clearInterval(id);
  }, [state.run.status]);

  const reset = () => {
    clearState();
    dispatch({ type: "RESET" });
  };
  const started = state.step !== "content" || state.lines.length > 0;

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14" data-tour="tool-podcast">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
          <h1 className="text-xl font-bold">{t("title")}</h1>
          {started && (
            <button type="button" onClick={reset} className={ACTION}>
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
            <PodcastStepper step={state.step} canEnter={(i) => reachable(i, state)} onStepClick={(i) => dispatch({ type: "GO", step: STEPS[i] })} />

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
                voices={voices}
                onCount={(count) => dispatch({ type: "SET_COUNT", count })}
                onPerson={(index, person) => dispatch({ type: "SET_PERSON", index, person })}
                onLength={(length) => dispatch({ type: "SET_LENGTH", length })}
                onStyle={(style) => dispatch({ type: "SET_STYLE", style })}
                onBack={() => dispatch({ type: "GO", step: "content" })}
                onNext={() => dispatch({ type: "GENERATE_START" })}
              />
            )}
            {state.step === "script" && (
              <ScriptStep
                lines={state.lines}
                persons={state.persons}
                count={state.count}
                generating={state.generating}
                run={state.run}
                onUpdate={(id, text) => dispatch({ type: "UPDATE_LINE", id, text })}
                onRephrase={(id) => dispatch({ type: "REPHRASE_LINE", id })}
                onDelete={(id) => dispatch({ type: "DELETE_LINE", id })}
                onAdd={() => dispatch({ type: "ADD_LINE" })}
                onBack={() => dispatch({ type: "GO", step: "cast" })}
                onVoice={() => dispatch({ type: "START_VOICING" })}
                onToDone={() => dispatch({ type: "GO", step: "done" })}
              />
            )}
            {state.step === "voicing" && (
              <VoicingStep
                lines={state.lines}
                persons={state.persons}
                run={state.run}
                onResume={() => dispatch({ type: "RESUME" })}
                onCancel={() => dispatch({ type: "CANCEL" })}
                onBackToScript={() => dispatch({ type: "GO", step: "script" })}
                onUpdate={(id, text) => dispatch({ type: "UPDATE_LINE", id, text })}
                onVoice={() => dispatch({ type: "START_VOICING" })}
                onWeiter={() => dispatch({ type: "GO", step: "done" })}
              />
            )}
            {state.step === "done" && (
              <DoneStep
                lines={state.lines}
                persons={state.persons}
                count={state.count}
                run={state.run}
                onUpdate={(id, text) => dispatch({ type: "UPDATE_LINE", id, text })}
                onVoice={() => dispatch({ type: "START_VOICING" })}
                onEditScript={() => dispatch({ type: "GO", step: "script" })}
                onReset={reset}
              />
            )}
          </>
        )}

        <p className="mt-10 text-xs text-muted-soft">{t("mockNote")}</p>
      </div>
    </ProtectedRoute>
  );
}
