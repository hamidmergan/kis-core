"use client";

import { useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import { driver, type Config, type Driver, type PopoverDOM } from "driver.js";
import { TOUR_STEPS } from "./steps";
import { demoSchritte, type DemoSchritt, type TourAktionen } from "./demoSteps";
import { merkeTourGesehen } from "./tourSeen";

/** Phosphor X in bold, the icon of the app, driver.js only offers a text times sign. */
const SCHLIESSEN_ICON = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256" aria-hidden="true"><path d="M208.49,191.51a12,12,0,0,1-17,17L128,145,64.49,208.49a12,12,0,0,1-17-17L111,128,47.51,64.49a12,12,0,0,1,17-17L128,111l63.51-63.52a12,12,0,0,1,17,17L145,128Z" /></svg>`;

interface StartOptionen {
  /** The demo course gets the long tour, it knows the files there. */
  demo?: boolean;
  aktionen?: TourAktionen;
  workspaceUuid?: string;
  /** Whoever may not create modules skips the owner stations, see demoSteps. */
  darfModuleAnlegen?: boolean;
}

/**
 * Drives the guided tour through the course.
 *
 * Two scripts: the short one for any course, and the long one for the demo
 * course, which opens materials and studio tabs itself (see demoSteps). Every
 * step can be left with "next", including the ones asking for an action, so
 * nobody gets stuck.
 */
export function useTour() {
  const t = useTranslations("workspace.detail.tour");
  const tAllgemein = useTranslations("common");
  const laufend = useRef<Driver | null>(null);

  /** driver.js builds its own buttons, this hands them the app classes. */
  const knoepfeAngleichen = useCallback((popover: PopoverDOM) => {
    popover.nextButton.classList.remove("driver-popover-footer-btn");
    popover.nextButton.classList.add("btn-primary", "text-sm", "rounded-lg", "px-4", "py-2");
    popover.previousButton.classList.remove("driver-popover-footer-btn");
    popover.previousButton.classList.add(
      "btn-ghost", "text-sm", "rounded-lg", "px-4", "py-2",
      "text-foreground-soft", "border", "border-border", "transition-colors",
    );
    popover.closeButton.classList.add(
      "w-7", "h-7", "flex", "items-center", "justify-center",
      "rounded-full", "btn-icon", "flex-shrink-0", "text-[var(--kb)]",
    );
    popover.closeButton.style.backgroundColor = "rgba(var(--kb-rgb),0.10)";
    // driver.js sets display as an inline style, which beats the flex class and
    // pushes the icon out of the middle. "none" means the step hides the button.
    if (popover.closeButton.style.display !== "none") popover.closeButton.style.display = "flex";
    popover.closeButton.setAttribute("aria-label", tAllgemein("close"));
    popover.closeButton.innerHTML = SCHLIESSEN_ICON;
  }, [tAllgemein]);

  /** First PDF in the source list, the selection bar only exists on those. */
  const erstePdfZeile = useCallback((): HTMLElement | null => {
    const zeilen = Array.from(document.querySelectorAll<HTMLElement>('[data-tour="source-row"]'));
    return zeilen.find((z) => /\.pdf\b/i.test(z.textContent ?? "")) ?? null;
  }, []);

  const grundEinstellungen = useCallback((): Config => ({
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
    onPopoverRender: knoepfeAngleichen,
    // Only the last step counts as done, so breaking off keeps the invitation
    // on the start page. driver.js hands the last step to this hook instead of
    // onNextClick, and taking the hook means closing up afterwards ourselves.
    onDoneClick: (_element, _schritt, opts) => {
      void merkeTourGesehen(true);
      opts.driver.destroy();
    },
    onDestroyed: () => {
      laufend.current = null;
    },
  }), [t, knoepfeAngleichen]);

  const startAllgemein = useCallback(() => {
    const vorhanden = TOUR_STEPS.filter((s) => {
      if (document.querySelector(`[data-tour="${s.anchor}"]`)) return true;
      // Its anchor appears only once an earlier step opened it.
      return s.opensOnDemand === true && erstePdfZeile() !== null;
    });
    if (vorhanden.length === 0) return;

    let fuehrung: Driver;
    fuehrung = driver({
      ...grundEinstellungen(),
      steps: vorhanden.map((s, i) => ({
        element: `[data-tour="${s.anchor}"]`,
        popover: {
          title: t(`steps.${s.key}.title`),
          description: t(`steps.${s.key}.text`),
          side: s.side,
          align: "start" as const,
          // The tour opens the PDF itself, so the selection bar step never
          // drops out just because nobody clicked a source beforehand. The key
          // is only set where it is needed: driver.js takes its presence as
          // "you handle next yourself", even when the value is undefined.
          ...(vorhanden[i + 1]?.opensOnDemand
            ? {
                onNextClick: () => {
                  erstePdfZeile()?.click();
                  window.setTimeout(() => fuehrung.moveNext(), 600);
                },
              }
            : {}),
        },
      })),
    });

    laufend.current = fuehrung;
    fuehrung.drive();
  }, [t, erstePdfZeile, grundEinstellungen]);

  const startDemo = useCallback(async (
    aktionen: TourAktionen,
    workspaceUuid?: string,
    darfModuleAnlegen = true,
  ) => {
    // Glossary entry and note live per person, so they are put in place for
    // whoever takes the tour. Without them two stations would stand empty.
    if (workspaceUuid) {
      await fetch("/api/ai-assistant/demo/tour-content", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_uuid: workspaceUuid }),
      }).catch(() => { /* Der Rundgang laeuft auch ohne die Beispiele. */ });
      // Die Seite stand schon, als die Beispiele entstanden, also neu holen.
      aktionen.beispieleLaden();
    }

    const schritte = demoSchritte(darfModuleAnlegen);
    const ziel = (s: DemoSchritt) => (s.ziel ? (() => s.ziel!() ?? undefined) : undefined);
    const springe = (s: DemoSchritt | undefined, weiter: () => void) => {
      s?.vorbereiten?.(aktionen);
      window.setTimeout(weiter, s?.vorbereiten ? s.wartezeit ?? 700 : 0);
    };

    let fuehrung: Driver;
    fuehrung = driver({
      ...grundEinstellungen(),
      steps: schritte.map((s, i) => ({
        element: ziel(s) as unknown as () => Element,
        popover: {
          title: t(`demo.${s.key}.title`),
          description: t(`demo.${s.key}.text`),
          side: s.side,
          align: "start" as const,
          // Each step opens what it points at, so the hook belongs to the step
          // being entered and not to the one being left. driver.js reads the
          // presence of the key as "you handle it yourself", therefore it is
          // only set where something has to be opened.
          ...(schritte[i + 1]?.vorbereiten
            ? { onNextClick: () => springe(schritte[i + 1], () => fuehrung.moveNext()) }
            : {}),
          ...(schritte[i - 1]?.vorbereiten
            ? { onPrevClick: () => springe(schritte[i - 1], () => fuehrung.movePrevious()) }
            : {}),
        },
      })),
    });

    laufend.current = fuehrung;
    springe(schritte[0], () => fuehrung.drive());
  }, [t, grundEinstellungen]);

  const start = useCallback((optionen?: StartOptionen) => {
    if (optionen?.demo && optionen.aktionen) {
      void startDemo(optionen.aktionen, optionen.workspaceUuid, optionen.darfModuleAnlegen);
      return;
    }
    startAllgemein();
  }, [startAllgemein, startDemo]);

  const stop = useCallback(() => {
    laufend.current?.destroy();
    laufend.current = null;
  }, []);

  return { start, stop };
}
