"use client";

import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import RegenChatModal, { type RegenTurn } from "@/components/regen/RegenChatModal";
import { applyRegen, type RegenApplyMode } from "@/components/regen/apply";
import Spinner from "@/components/ui/Spinner";
import ToolBackLink from "@/components/ui/ToolBackLink";
import { usePermissions } from "@/hooks/usePermissions";
import { useRegenAnchor } from "@/hooks/useRegenAnchor";
import { useActiveJobCheck } from "@/hooks/useScreencastResume";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { notifyJobsChanged } from "@/lib/jobs-events";
import * as api from "./_api";
import PraesentationStepper from "./_components/PraesentationStepper";
import { LAEUFT, reachable, closedForGood } from "./_logic";
import { INITIAL_STATE, reducer, type Action } from "./_reducer";
import ContentStep from "./_steps/ContentStep";
import DoneStep from "./_steps/DoneStep";
import SlidesStep from "./_steps/SlidesStep";
import { STEPS, type Language, type Slide, type Step } from "./_types";

const POLL_MS = 2000;
const SAVE_MS = 800;

function PraesentationPageInner() {
  const t = useTranslations("tools.praesentation");
  const tCommon = useTranslations("common");
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  // The chat model that writes, picked in the first step and sent along with the start.
  const llm = useFeatureProviders("/praesentation/providers");
  const { permissions } = usePermissions();
  const [hasActiveJob] = useActiveJobCheck("praesentation");
  const ausListe = useSearchParams().get("job");
  const regen = useRegenAnchor();
  const [regenArt, setRegenArt] = useState<"row" | "slide">("row");
  const [restored, setRestored] = useState(false);
  // Until the job param is restored and the active-job check has answered, the empty form must not flash.
  const hydrated = restored && hasActiveJob !== null;
  const stateRef = useRef(state);
  stateRef.current = state;
  const aenderung = useRef(0);
  const bautRef = useRef(false);

  /** Reads outline, slides and previews, and puts the page on the step the job is at. */
  const holeStand = useCallback(async (uuid: string, schrittSetzen = false) => {
    const vorher = stateRef.current.jobStatus;
    const view = await api.fetchPraesentation(uuid);
    // A job that just stopped running must refetch every preview, the browser would otherwise show the cached old one.
    const bump = (vorher === "running" || vorher === "pending" || vorher === "waiting_retry")
      && (view.status === "awaiting_user" || view.status === "success");
    dispatch({ type: "VIEW", outline: view.outline, slides: view.slides, previews: view.previews,
               missingImages: view.missing_images, hasDeck: view.has_deck, templateFallback: !!view.params?.template_fallback, bump });
    dispatch({ type: "JOB", status: view.status, progress: view.progress, error: view.error });
    if (view.params) {
      dispatch({ type: "RESTORE", state: { notes: view.params.notes, notesInclude: view.params.notes_include,
                 language: view.params.language as Language, instructions: view.params.instructions,
                 presenter: view.params.presenter ?? "",
                 templateId: view.params.template_id } });
    }
    if (schrittSetzen) {
      if (view.status === "success") dispatch({ type: "GO", step: "done" });
      else dispatch({ type: "GO", step: "slides" });
    }
    return view;
  }, []);

  useEffect(() => {
    if (!ausListe) {
      setRestored(true);
      return;
    }
    dispatch({ type: "RESTORE", state: { jobUuid: ausListe, maxReached: 1 } });
    holeStand(ausListe, true)
      .catch(() => dispatch({ type: "FAIL", error: tCommon("unknownError") }))
      .finally(() => setRestored(true));
  }, [ausListe, holeStand, tCommon]);

  useEffect(() => {
    const uuid = state.jobUuid;
    if (!uuid || !LAEUFT.has(state.jobStatus)) return;
    let abgebrochen = false;
    const id = window.setInterval(async () => {
      try {
        const job = await api.fetchJob(uuid);
        if (abgebrochen) return;
        dispatch({ type: "JOB", status: job.status, progress: job.progress, error: job.error });
        if (!LAEUFT.has(job.status)) {
          await holeStand(uuid);
          notifyJobsChanged();
        }
      } catch { /* a single lost poll means nothing */ }
    }, POLL_MS);
    return () => { abgebrochen = true; window.clearInterval(id); };
  }, [state.jobUuid, state.jobStatus, holeStand]);

  const melde = (e: unknown) => dispatch({ type: "FAIL", error: e instanceof Error && e.message ? e.message : tCommon("unknownError") });

  const starten = async () => {
    dispatch({ type: "STARTING" });
    try {
      const uuid = await api.startPraesentation(stateRef.current, llm.providerId);
      dispatch({ type: "STARTED", jobUuid: uuid });
      notifyJobsChanged();
    } catch (e) {
      melde(e);
      dispatch({ type: "GO", step: "content" });
    }
  };

  // Every edit debounces its own save, keyed per target so an outline save and a slide save never cancel each other.
  type PendingSave = { timer: number; run: () => Promise<void> };
  const speicherMap = useRef<Map<string, PendingSave>>(new Map());

  // Clears any pending save timers left over once the page unmounts.
  useEffect(() => () => {
    for (const eintrag of speicherMap.current.values()) window.clearTimeout(eintrag.timer);
  }, []);

  const planeSpeichern = (key: string, run: () => Promise<void>) => {
    const bestehend = speicherMap.current.get(key);
    if (bestehend) window.clearTimeout(bestehend.timer);
    const timer = window.setTimeout(() => {
      speicherMap.current.delete(key);
      run().catch(melde);
    }, SAVE_MS);
    speicherMap.current.set(key, { timer, run });
  };

  // Runs every still-pending save right away, used before a step that needs the latest state on the server.
  const flushSaves = async () => {
    const eintraege = [...speicherMap.current.values()];
    for (const eintrag of eintraege) window.clearTimeout(eintrag.timer);
    speicherMap.current.clear();
    await Promise.all(eintraege.map((eintrag) => eintrag.run().catch(melde)));
  };

  const outlineAendern = (action: Action) => {
    dispatch(action);
    const marke = ++aenderung.current;
    planeSpeichern("outline", async () => {
      const s = stateRef.current;
      if (!s.jobUuid || !s.outline) return;
      const gespeichert = await api.saveOutline(s.jobUuid, s.outline);
      // Only adopt while nothing newer happened, the server hands out the ids.
      if (marke === aenderung.current) dispatch({ type: "RESTORE", state: { outline: gespeichert } });
    });
  };

  const bauen = async () => {
    if (bautRef.current) return;
    bautRef.current = true;
    try {
      await flushSaves();
      const s = stateRef.current;
      if (!s.jobUuid || !s.outline) return;
      await api.saveOutline(s.jobUuid, s.outline);
      await api.startBuild(s.jobUuid);
      dispatch({ type: "JOB", status: "pending", progress: { step: "texte" } });
      dispatch({ type: "GO", step: "slides" });
    } catch (e) { melde(e); } finally { bautRef.current = false; }
  };

  const folieAendern = (slide: Slide) => {
    dispatch({ type: "UPDATE_SLIDE", slide });
    planeSpeichern(`slide:${slide.id}`, async () => {
      const s = stateRef.current;
      const aktuell = s.slides.find((x) => x.id === slide.id);
      if (!s.jobUuid || !aktuell) return;
      await api.saveSlide(s.jobUuid, aktuell);
      dispatch({ type: "PREVIEW_FRESH", id: slide.id });
    });
  };

  const mitStand = async (arbeit: (uuid: string) => Promise<unknown>) => {
    const uuid = stateRef.current.jobUuid;
    if (!uuid) return;
    try {
      await arbeit(uuid);
      await holeStand(uuid);
    } catch (e) { melde(e); }
  };

  // Slides whose number changed come back re-rendered, the browser must not show the cached picture.
  const nummernFrisch = (antwort: { previews?: string[] }) => {
    for (const id of antwort.previews ?? []) dispatch({ type: "PREVIEW_FRESH", id });
  };

  const finalisieren = async () => {
    await flushSaves();
    await mitStand(async (u) => {
      await api.finalize(u);
      dispatch({ type: "JOB", status: "pending", progress: { step: "bau" } });
    });
  };

  const regenZiel = regen.regeneratingSlide;
  const regenRow = regenArt === "row" && regenZiel !== null ? state.outline?.rows[regenZiel] ?? null : null;
  const regenSlide = regenArt === "slide" && regenZiel !== null ? state.slides[regenZiel] ?? null : null;

  const vorschlagen = async (messages: RegenTurn[]) => {
    const uuid = stateRef.current.jobUuid;
    if (!uuid) return "";
    if (regenRow) {
      const r = await api.regenRow(uuid, regenRow.id, messages, regen.anchorText);
      return `${r.title}\n${r.gist}`;
    }
    if (regenSlide) {
      const s = await api.regenSlide(uuid, regenSlide.id, messages, regen.anchorText);
      return JSON.stringify(s);
    }
    return "";
  };

  const uebernehmen = (mode: RegenApplyMode, content: string) => {
    if (regenRow) {
      const [title, ...rest] = content.split("\n");
      outlineAendern({ type: "UPDATE_ROW", row: { ...regenRow, title: title.trim() || regenRow.title,
                       gist: applyRegen(regenRow.gist, regen.anchorText, mode, rest.join(" ").trim()) } });
    } else if (regenSlide) {
      try {
        const neu = JSON.parse(content) as Slide;
        folieAendern({ ...neu, id: regenSlide.id, role: regenSlide.role, layout: regenSlide.layout });
      } catch {
        melde(new Error(t("regenChat.notJson")));
      }
    }
    regen.close();
  };

  const gehe = (i: number) => dispatch({ type: "GO", step: STEPS[i] as Step });

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14" data-tour="tool-praesentation">
        <ToolBackLink />
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="text-sm text-muted mt-1 mb-8">{t("intro")}</p>
        {!hydrated ? (
          <Spinner className="justify-center py-20" />
        ) : (
          <>
            {state.step !== "content" && (
              <PraesentationStepper step={state.step} canEnter={(i) => reachable(i, state)}
                                    isClosedForGood={(i) => closedForGood(i, state)} onStepClick={gehe} />
            )}
            {state.step === "content" && (
              <ContentStep canUseModules={!!permissions.allow_aia} source={state.source} language={state.language}
                notes={state.notes} instructions={state.instructions} presenter={state.presenter} templateId={state.templateId}
                hasActiveJob={hasActiveJob} error={state.error}
                llmProviders={llm.providers} llmProviderId={llm.providerId} onLlmProvider={llm.setProviderId}
                onSource={(source) => dispatch({ type: "SET_SOURCE", source })}
                onLanguage={(language) => dispatch({ type: "SET_LANGUAGE", language })}
                onNotes={(notes) => dispatch({ type: "SET_NOTES", notes })}
                onInstructions={(text) => dispatch({ type: "SET_INSTRUCTIONS", text })}
                onPresenter={(name) => dispatch({ type: "SET_PRESENTER", name })}
                onTemplate={(templateId) => dispatch({ type: "SET_TEMPLATE", templateId })}
                onNext={starten} />
            )}
            {state.step === "slides" && state.jobUuid && (
              <SlidesStep jobUuid={state.jobUuid} slides={state.slides} previews={state.previews} missingImages={state.missingImages}
                notesOn={state.notes} notesInclude={state.notesInclude}
                onNotesInclude={(include) => { dispatch({ type: "SET_NOTES_INCLUDE", include }); mitStand(async (u) => { await api.setNotesInclude(u, include); }); }}
                jobStatus={state.jobStatus} progress={state.progress} error={state.error}
                onSlide={folieAendern}
                onMove={(id, delta) => { dispatch({ type: "MOVE_SLIDE", id, delta }); const ids = reducer(stateRef.current, { type: "MOVE_SLIDE", id, delta }).slides.map((s) => s.id); mitStand(async (u) => nummernFrisch(await api.saveOrder(u, ids))); }}
                onDelete={(id) => mitStand(async (u) => nummernFrisch(await api.deleteSlide(u, id)))}
                onInsertAfter={(id, title, instruction) => mitStand(async (u) => { await api.insertSlide(u, id, title, instruction); dispatch({ type: "JOB", status: "pending", progress: { step: "texte" } }); })}
                onRegenText={(i) => { setRegenArt("slide"); regen.open(i); }}
                onRegenImage={(id, prompts) => mitStand(async (u) => { await api.regenImage(u, id, prompts); dispatch({ type: "JOB", status: "pending", progress: { step: "bilder" } }); })}
                onAnchor={regen.setAnchor}
                hasOutline={!!state.outline}
                onRestart={() => dispatch({ type: "RESET" })}
                onResume={() => mitStand(async (u) => { await api.startBuild(u); dispatch({ type: "JOB", status: "pending", progress: { step: "texte" } }); })}
                onFinalize={finalisieren} />
            )}
            {state.step === "done" && state.jobUuid && (
              <DoneStep jobUuid={state.jobUuid} slides={state.slides.length}
                onBackToSlides={() => dispatch({ type: "GO", step: "slides" })}
                onNew={() => dispatch({ type: "RESET" })} />
            )}
            {(regenRow || regenSlide) && (
              <RegenChatModal index={regenZiel ?? 0} namespace="tools.praesentation.regenChat" anchorText={regen.anchorText}
                              onSend={vorschlagen} onApply={uebernehmen} onClose={regen.close} />
            )}
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function PraesentationPage() {
  return (
    <Suspense fallback={null}>
      <PraesentationPageInner />
    </Suspense>
  );
}
