"use client";

import { useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import { driver, type Driver, type PopoverDOM } from "driver.js";
import { useRouter } from "@/i18n/navigation";
import type { ToolKey } from "@/lib/modules";
import { knoepfeAngleichen } from "./popoverStil";
import { merkeWerkzeugTourGesehen } from "./toolsTourSeen";
import { werkzeugRundgang, type RundgangSchritt } from "./toolsSteps";

/** Longest wait for a station's target, generous because a whole page has to arrive first. */
const ZIEL_HOECHSTENS_MS = 10000;
/** Once the page itself stands, its anchor is a few frames away at most, so a station whose target is simply not there stops waiting here. */
const OHNE_ANKER_MS = 2000;
/** Shortest pause after a jump, a fresh page needs a frame or two to draw. */
const ZIEL_MINDESTENS_MS = 250;
const ZIEL_TAKT_MS = 100;
/** A click this soon after a jump is the tail of a double click, driver.js is still fading the new station in. */
const DOPPELKLICK_MS = 500;
/** Below this the open sidebar covers the whole page, exactly as in ToolsSidebar. */
const BREIT = "(min-width: 1024px)";

export interface RundgangAktionen {
  /** Opens or collapses the sidebar, the first station needs it open and a narrow screen needs it out of the way. */
  seitenleiste: (offen: boolean) => void;
}

function ziel(anker: string): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[data-tour="${anker}"]`);
}

/** A station only carries its weight while its target is drawn, the jobs entry is hidden on a phone. */
function zielSichtbar(anker: string): boolean {
  const el = ziel(anker);
  return el !== null && el.offsetParent !== null;
}

/**
 * Drives the guided tour through the tools.
 *
 * Unlike the tour through a course this one changes the page: it opens every
 * tool itself, because the name in the sidebar says what a tool is called and
 * nothing about what it wants. The layout around the tools stays mounted while
 * the page below it changes, which is what lets one driver.js run across all
 * of them.
 *
 * The tour opens and shows, it never sends anything off.
 */
export function useToolsTour() {
  const t = useTranslations("toolsTour");
  const tAllgemein = useTranslations("common");
  const router = useRouter();
  const laufend = useRef<Driver | null>(null);

  const start = useCallback((sichtbar: readonly ToolKey[], aktionen: RundgangAktionen) => {
    laufend.current?.destroy();

    // A station on a tool page is judged only once that page stands, everything
    // else has to be on the page already.
    const schritte = werkzeugRundgang(sichtbar).filter((s) => s.route || s.ohneZiel || zielSichtbar(s.anker));
    if (schritte.length === 0) return;

    const breit = () => window.matchMedia(BREIT).matches;
    /** The sidebar stays beside the tool on a wide screen, on a narrow one it would cover it. */
    const vorbereiten = (s: RundgangSchritt) => {
      aktionen.seitenleiste(s.route ? breit() : true);
      if (s.route) router.push(s.route);
    };

    let fuehrung: Driver;
    // One jump at a time, a second click while a station still loads would skip the next one.
    let unterwegs = false;
    let letzterSprung = 0;

    /** Greys the footer buttons out while the next station loads, driver.js builds fresh ones for it. */
    const knoepfeSperren = () => {
      const popover = fuehrung.getState("popover") as PopoverDOM | undefined;
      for (const knopf of [popover?.nextButton, popover?.previousButton]) {
        if (!knopf) continue;
        knopf.disabled = true;
        knopf.classList.add("driver-popover-btn-disabled");
      }
    };

    /** Opens what a station points at and moves on once it stands, capped so a missing anchor never stalls the tour. */
    const springe = (s: RundgangSchritt | undefined, weiter: () => void) => {
      if (unterwegs || Date.now() - letzterSprung < DOPPELKLICK_MS) return;
      const los = () => { letzterSprung = Date.now(); unterwegs = false; weiter(); };
      if (!s) { los(); return; }
      unterwegs = true;
      knoepfeSperren();
      vorbereiten(s);
      const start = Date.now();
      let seiteSeit: number | null = null;
      const pruefen = () => {
        const el = ziel(s.anker);
        const gewartet = Date.now() - start;
        if (seiteSeit === null && (!s.route || window.location.pathname.endsWith(s.route))) {
          seiteSeit = Date.now();
        }
        // A tool can hide its entry, the screencast does while it resumes a
        // running job. Waiting the full cap for that anchor would freeze the
        // tour, so the arrived page ends the wait on its own.
        const ohneAnker = s.ohneZiel || (seiteSeit !== null && Date.now() - seiteSeit >= OHNE_ANKER_MS);
        if ((el !== null && gewartet >= ZIEL_MINDESTENS_MS) || ohneAnker || gewartet >= ZIEL_HOECHSTENS_MS) {
          el?.scrollIntoView({ block: "center", inline: "nearest" });
          los();
          return;
        }
        window.setTimeout(pruefen, ZIEL_TAKT_MS);
      };
      pruefen();
    };

    // Whoever closed the tour while a station was still loading gets no late jump.
    const solangeAktiv = (weiter: () => void) => () => { if (fuehrung.isActive()) weiter(); };

    fuehrung = driver({
      showProgress: true,
      allowClose: true,
      // A click beside the popover must not end the tour, the X and Escape do that.
      overlayClickBehavior: () => {},
      overlayOpacity: 0.6,
      // Half of the smallest cut-out, so the ring around a round button is round too.
      stageRadius: 24,
      nextBtnText: t("next"),
      prevBtnText: t("back"),
      doneBtnText: t("done"),
      progressText: t("progress", { current: "{{current}}", total: "{{total}}" }),
      popoverClass: "kis-tour",
      onPopoverRender: (popover) => knoepfeAngleichen(popover, tAllgemein("close")),
      // Only the last station counts as done, so breaking off keeps the
      // invitation on the start page. Taking the hook means closing up here.
      onDoneClick: (_element, _schritt, opts) => {
        void merkeWerkzeugTourGesehen(true);
        opts.driver.destroy();
      },
      onDestroyed: () => { laufend.current = null; },
      steps: schritte.map((s, i) => ({
        element: (() => ziel(s.anker) ?? undefined) as unknown as () => Element,
        popover: {
          title: t(`${s.key}.title`),
          description: t(`${s.key}.text`),
          side: s.side,
          align: "start" as const,
          // Each station opens what it points at, so the hook belongs to the
          // one being entered. driver.js reads the presence of the key as "you
          // handle it yourself", so the last station keeps none and its "done"
          // closes the tour.
          ...(i + 1 < schritte.length
            ? { onNextClick: () => springe(schritte[i + 1], solangeAktiv(() => fuehrung.moveNext())) }
            : {}),
          ...(i > 0
            ? { onPrevClick: () => springe(schritte[i - 1], solangeAktiv(() => fuehrung.movePrevious())) }
            : {}),
        },
      })),
    });

    laufend.current = fuehrung;
    springe(schritte[0], () => fuehrung.drive());
    // The start is no jump, the first click must not fall into the double click window.
    letzterSprung = 0;
  }, [t, tAllgemein, router]);

  const stop = useCallback(() => {
    laufend.current?.destroy();
    laufend.current = null;
  }, []);

  return { start, stop };
}
