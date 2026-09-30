"use client";

import { Trash } from "@phosphor-icons/react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import RegenChatModal, { type RegenTurn } from "@/components/regen/RegenChatModal";
import { applyRegen, type RegenApplyMode } from "@/components/regen/apply";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import ToolBackLink from "@/components/ui/ToolBackLink";
import { usePermissions } from "@/hooks/usePermissions";
import { useRegenAnchor } from "@/hooks/useRegenAnchor";
import { useActiveJobCheck } from "@/hooks/useScreencastResume";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { notifyJobsChanged } from "@/lib/jobs-events";
import * as api from "./_api";
import PraesentationStepper from "./_components/PraesentationStepper";
import { LAEUFT, closedForGood, isBusy, reachable, schrittFuer } from "./_logic";
import { INITIAL_STATE, reducer, type Action } from "./_reducer";
import ContentStep from "./_steps/ContentStep";
import DoneStep from "./_steps/DoneStep";
import PreviewStep from "./_steps/PreviewStep";
import { STEPS, type Language, type Slide, type Step } from "./_types";

const POLL_MS = 2000;
const SAVE_MS = 800;
const DISCARD = "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-soft transition-colors hover:text-error focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb";

function PraesentationPageInner() {
  const t = useTranslations("tools.praesentation");
  const tCommon = useTranslations("common");
  const tNachfrage = useTranslations("tools.praesentation.nachfrage");
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const [nachfrage, setNachfrage] = useState<"abbrechen" | "verwerfen" | null>(null);
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
               missingImages: view.missing_images, images: view.images ?? {}, hasDeck: view.has_deck,
               templateFallback: !!view.params?.template_fallback, bump });
    dispatch({ type: "JOB", status: view.status, progress: view.progress, error: view.error });
    if (view.params) {
      dispatch({ type: "RESTORE", state: { notes: view.params.notes, notesInclude: view.params.notes_include,
                 language: view.params.language as Language, instructions: view.params.instructions,
                 presenter: view.params.presenter ?? "",
                 templateId: view.params.template_id } });
    }
    if (schrittSetzen) dispatch({ type: "GO", step: schrittFuer(view.status, view.progress) });
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
    let belegt = false;
    let zuletzt = "";
    const id = window.setInterval(async () => {
      if (belegt) return;
      belegt = true;
      try {
        const job = await api.fetchJob(uuid);
        if (abgebrochen) return;
        if (!LAEUFT.has(job.status)) {
          // The view first, so the step that follows already has its previews.
          await holeStand(uuid);
          notifyJobsChanged();
          return;
        }
        dispatch({ type: "JOB", status: job.status, progress: job.progress, error: job.error });
        // Each finished wave of texts and each drawn picture moves the counter, the sketch then fetches what is new.
        const marke = `${job.progress?.step ?? ""}:${job.progress?.current ?? ""}`;
        if (marke !== zuletzt) {
          zuletzt = marke;
          await holeStand(uuid);
        }
      } catch { /* a single lost poll means nothing */ } finally { belegt = false; }
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
      dispatch({ type: "GO", step: "preview" });
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
      // The server sets a finished deck back to draft, the download waits for the next finalize.
      if (stateRef.current.jobStatus === "success") dispatch({ type: "JOB", status: "awaiting_user", progress: stateRef.current.progress });
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
      dispatch({ type: "JOB", status: "pending", progress: { step: "bau", final: true } });
      dispatch({ type: "GO", step: "done" });
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

  // A deleted job must not come back from the address on the next reload.
  const ohneAuftragInAdresse = () => {
    if (ausListe) window.history.replaceState(null, "", window.location.pathname);
  };

  // Before the outline nothing is lost, the job goes and the first step comes back, like the screencast before its scripts.
  const abbrechen = async () => {
    setNachfrage(null);
    const uuid = stateRef.current.jobUuid;
    if (!uuid) return;
    if (!stateRef.current.outline) {
      await api.deleteJob(uuid);
      ohneAuftragInAdresse();
      dispatch({ type: "BACK_TO_START" });
    } else {
      await api.cancelJob(uuid);
      dispatch({ type: "JOB", status: "awaiting_user", progress: null, error: null });
      dispatch({ type: "GO", step: "preview" });
      await holeStand(uuid).catch(melde);
    }
    notifyJobsChanged();
  };

  const verwerfen = async () => {
    setNachfrage(null);
    const uuid = stateRef.current.jobUuid;
    if (uuid) await api.deleteJob(uuid);
    ohneAuftragInAdresse();
    dispatch({ type: "RESET" });
    notifyJobsChanged();
  };

  const gehe = (i: number) => dispatch({ type: "GO", step: STEPS[i] as Step });

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-10 sm:py-14" data-tour="tool-praesentation">
        <ToolBackLink />
        {/* Title and intro only on the first step, like podcast and screencast. */}
        {hydrated && state.step === "content" ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-2xl font-bold">{t("title")}</h1>
              {state.jobUuid && (
                <button type="button" onClick={() => setNachfrage("verwerfen")} className={DISCARD}>
                  <Trash size={14} aria-hidden="true" />
                  {t("discard")}
                </button>
              )}
            </div>
            <p className="text-sm text-muted mt-1 mb-8">{t("intro")}</p>
          </>
        ) : hydrated && state.jobUuid && (
          <div className="flex justify-end mb-3 sm:mb-8">
            <button type="button" onClick={() => setNachfrage("verwerfen")} className={DISCARD}>
              <Trash size={14} aria-hidden="true" />
              {t("discard")}
            </button>
          </div>
        )}
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
                notes={state.notes} instructions={state.instructions} imageStyle={state.imageStyle}
                presenter={state.presenter} templateId={state.templateId}
                hasActiveJob={hasActiveJob} error={state.error}
                llmProviders={llm.providers} llmProviderId={llm.providerId} onLlmProvider={llm.setProviderId}
                onSource={(source) => dispatch({ type: "SET_SOURCE", source })}
                onLanguage={(language) => dispatch({ type: "SET_LANGUAGE", language })}
                onNotes={(notes) => dispatch({ type: "SET_NOTES", notes })}
                onInstructions={(text) => dispatch({ type: "SET_INSTRUCTIONS", text })}
                onImageStyle={(text) => dispatch({ type: "SET_IMAGE_STYLE", text })}
                onPresenter={(name) => dispatch({ type: "SET_PRESENTER", name })}
                onTemplate={(templateId) => dispatch({ type: "SET_TEMPLATE", templateId })}
                onNext={starten} />
            )}
            {/* The cards stand from the click on start, before the job even has its id. */}
            {state.step === "preview" && (state.jobUuid || state.starting) && (
              <PreviewStep jobUuid={state.jobUuid ?? ""} outline={state.outline} slides={state.slides} previews={state.previews}
                images={state.images} missingImages={state.missingImages} inArbeit={state.inArbeit} presenter={state.presenter}
                notesOn={state.notes} notesInclude={state.notesInclude} laeuft={isBusy(state)}
                jobStatus={state.jobStatus} progress={state.progress} error={state.error} hasOutline={!!state.outline}
                hasDeck={state.hasDeck}
                onNotesInclude={(include) => { dispatch({ type: "SET_NOTES_INCLUDE", include }); mitStand(async (u) => { await api.setNotesInclude(u, include); }); }}
                onSlide={folieAendern}
                onMove={(id, delta) => { dispatch({ type: "MOVE_SLIDE", id, delta }); const ids = reducer(stateRef.current, { type: "MOVE_SLIDE", id, delta }).slides.map((s) => s.id); mitStand(async (u) => nummernFrisch(await api.saveOrder(u, ids))); }}
                onDelete={(id) => mitStand(async (u) => nummernFrisch(await api.deleteSlide(u, id)))}
                onInsertAfter={(id, title, instruction) => mitStand(async (u) => {
                  const neu = await api.insertSlide(u, id, title, instruction);
                  dispatch({ type: "IN_ARBEIT", ids: [neu.id] });
                  dispatch({ type: "JOB", status: "pending", progress: { step: "texte" } });
                })}
                onRegenImage={(id, prompts) => mitStand(async (u) => {
                  await api.regenImage(u, id, prompts);
                  dispatch({ type: "IN_ARBEIT", ids: [id] });
                  dispatch({ type: "JOB", status: "pending", progress: { step: "bilder" } });
                })}
                onAnchor={regen.setAnchor}
                onRestart={() => dispatch({ type: "RESET" })}
                onCancel={state.jobUuid ? () => setNachfrage("abbrechen") : null}
                onResume={() => mitStand(async (u) => { await api.startBuild(u); dispatch({ type: "JOB", status: "pending", progress: { step: "texte" } }); })}
                onFinalize={finalisieren} />
            )}
            {state.step === "done" && state.jobUuid && (
              <DoneStep jobUuid={state.jobUuid} slides={state.slides} previews={state.previews}
                jobStatus={state.jobStatus} progress={state.progress} error={state.error}
                onResume={() => mitStand(async (u) => { await api.startBuild(u); dispatch({ type: "JOB", status: "pending", progress: { step: "bau", final: true } }); })}
                onBackToPreview={() => dispatch({ type: "GO", step: "preview" })}
                onNew={() => dispatch({ type: "RESET" })}
                onCancel={() => setNachfrage("abbrechen")} />
            )}
            {(regenRow || regenSlide) && (
              <RegenChatModal index={regenZiel ?? 0} namespace="tools.praesentation.regenChat" anchorText={regen.anchorText}
                              onSend={vorschlagen} onApply={uebernehmen} onClose={regen.close} />
            )}
            {nachfrage && (
              <Modal open onClose={() => setNachfrage(null)} size="sm"
                title={nachfrage === "verwerfen" ? tNachfrage("verwerfenTitel") : tNachfrage("abbrechenTitel")}
                footer={<>
                  <button type="button" onClick={() => setNachfrage(null)} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
                    {nachfrage === "verwerfen" ? tNachfrage("verwerfenNein") : tNachfrage("abbrechenNein")}
                  </button>
                  <button type="button" onClick={nachfrage === "verwerfen" ? verwerfen : abbrechen} className="px-4 py-2 text-sm btn-danger rounded-lg">
                    {nachfrage === "verwerfen" ? tNachfrage("verwerfenJa") : tNachfrage("abbrechenJa")}
                  </button>
                </>}>
                {nachfrage === "verwerfen" ? (
                  <>
                    <p className="text-sm text-foreground-soft">{tNachfrage("verwerfenText")}</p>
                    <p className="text-sm text-error mt-2">{tNachfrage("verwerfenWarnung")}</p>
                  </>
                ) : (
                  <p className="text-sm text-foreground-soft">
                    {state.outline ? tNachfrage("abbrechenText") : tNachfrage("abbrechenTextAnfang")}
                  </p>
                )}
              </Modal>
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
