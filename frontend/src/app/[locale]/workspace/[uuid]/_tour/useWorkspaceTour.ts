"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import type { PanelKey, Source, StudioView } from "../_types";
import type { StudioTab } from "../_hooks/useStudioTabs";
import type { TourAktionen } from "./demoSteps";
import { useTour } from "./useTour";

interface UseWorkspaceTourOptions {
  uuid: string;
  initialized: boolean;
  /** Arrived via the tour link (?tour=1), the tour then starts by itself. */
  tourAngefordert: boolean;
  istDemoModul: boolean;
  /** Without the right to create modules there are no tour steps pointing at the owner buttons. */
  darfModuleAnlegen: boolean;
  sources: Source[];
  openChapter: (chapterUuid: string) => void;
  setSelectedSourceIds: (ids: string[]) => void;
  openViewer: (source: Source) => void;
  closeViewer: () => void;
  setStudioView: (view: StudioView) => void;
  openStudioTab: (tab: StudioTab) => void;
  showPanel: (key: PanelKey) => void;
  loadGlossary: () => unknown;
  loadGlossaryCount: () => unknown;
  loadNotes: () => unknown;
  loadMessages: () => unknown;
  loadStreak: () => unknown;
  bumpStats: () => void;
}

/** Wires the guided tour to the workspace: what it may open, tick and switch, it never sends. */
export function useWorkspaceTour(opts: UseWorkspaceTourOptions) {
  const { uuid, initialized, tourAngefordert } = opts;
  const { start: startTour } = useTour();

  // Read through a ref, the tour calls these long after the render that started it.
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const aktionen = useMemo<TourAktionen>(() => {
    const quelleNachName = (dateiPraefix: string) =>
      optsRef.current.sources.find((s) => s.filename.startsWith(dateiPraefix));
    return {
      nurWaehlen: (dateiPraefix) => {
        const quelle = quelleNachName(dateiPraefix);
        if (!quelle) return;
        // A row inside a folded chapter is not on the page, so its chapter opens first.
        if (quelle.chapter_uuid) optsRef.current.openChapter(quelle.chapter_uuid);
        optsRef.current.setSelectedSourceIds([quelle.uuid]);
      },
      oeffnen: (dateiPraefix) => {
        const quelle = quelleNachName(dateiPraefix);
        if (quelle) optsRef.current.openViewer(quelle);
      },
      studioReiter: (reiter) => {
        optsRef.current.setStudioView("overview");
        optsRef.current.openStudioTab(reiter);
      },
      materialListe: () => {
        // The panel shows either the list or an opened viewer, the list needs both closed.
        optsRef.current.closeViewer();
        optsRef.current.showPanel("quellen");
      },
      beispieleLaden: () => {
        void optsRef.current.loadGlossary();
        void optsRef.current.loadGlossaryCount();
        // Tools and exercise history are also created only after the page has rendered.
        optsRef.current.bumpStats();
        void optsRef.current.loadStreak();
        void optsRef.current.loadNotes();
      },
      chatBeispielZeigen: () => {
        // On narrow screens the studio still covers the chat from the step before.
        optsRef.current.showPanel("chat");
        fetch("/api/ai-assistant/demo/tour-chat-example", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace_uuid: uuid }),
        })
          .then(() => optsRef.current.loadMessages())
          .catch(() => { /* Without the example the chat stays empty, not an error. */ });
      },
    };
  }, [uuid]);

  const starteRundgang = useCallback(() => {
    startTour({
      demo: optsRef.current.istDemoModul,
      aktionen,
      workspaceUuid: uuid,
      darfModuleAnlegen: optsRef.current.darfModuleAnlegen,
    });
  }, [startTour, uuid, aktionen]);

  const tourGestartet = useRef(false);
  useEffect(() => {
    if (!initialized || !tourAngefordert || tourGestartet.current) return;
    tourGestartet.current = true;
    // The panels need a moment, otherwise the first step points at nothing.
    const timer = window.setTimeout(() => {
      starteRundgang();
      // Remove the flag from the URL only now, otherwise every reload restarts the tour and an earlier access clears the start timer.
      const url = new URL(window.location.href);
      url.searchParams.delete("tour");
      window.history.replaceState({}, "", url.toString());
    }, 700);
    return () => window.clearTimeout(timer);
  }, [initialized, tourAngefordert, starteRundgang]);

  return { starteRundgang };
}
