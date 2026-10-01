"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";

interface SchrittReiterProps {
  /** The visible name of every step, in order. */
  labels: string[];
  current: number;
  canEnter: (index: number) => boolean;
  /** A step that can never be entered again, shown faded. */
  isClosedForGood?: (index: number) => boolean;
  /** A step left out of this run, shown struck through. */
  isSkipped?: (index: number) => boolean;
  onStepClick: (index: number) => void;
}

/** Numbered circles in a light band, scrolling sideways where the screen is too narrow, shared by the multi-step tools. */
export default function SchrittReiter({ labels, current, canEnter, isClosedForGood, isSkipped, onStepClick }: SchrittReiterProps) {
  const t = useTranslations("stepper");
  const leiste = useRef<HTMLOListElement>(null);

  // On a narrow screen the band scrolls sideways, the current step stays in view.
  useEffect(() => {
    const box = leiste.current;
    const el = box?.children[current] as HTMLElement | undefined;
    if (box && el && box.scrollWidth > box.clientWidth) {
      box.scrollTo({ left: el.offsetLeft - box.clientWidth / 2 + el.clientWidth / 2, behavior: "smooth" });
    }
  }, [current]);

  // With many steps only the current one keeps its name, the others stay circles with a tooltip.
  const nurAktuellerName = labels.length > 5;

  return (
    <>
      <nav aria-label={t("ariaLabel")} className="mt-4 mb-6 sm:mt-6 sm:mb-10">
        <ol ref={leiste} className="flex items-center gap-2.5 overflow-x-auto scrollbar-hide rounded-2xl border border-border-soft bg-surface px-4 py-3.5 sm:px-7 sm:py-5">
          {labels.map((label, i) => {
            const aktiv = i === current;
            const erledigt = i < current;
            const klickbar = !aktiv && canEnter(i);
            const tot = !aktiv && !klickbar && !!isClosedForGood?.(i);
            const weg = !!isSkipped?.(i);
            const Huelle = klickbar ? "button" : "span";
            return (
              <li key={i} className={`flex items-center gap-2.5 shrink-0 ${i < labels.length - 1 ? "flex-1" : ""}`}>
                <Huelle
                  {...(klickbar ? { type: "button" as const, onClick: () => onStepClick(i) } : {})}
                  title={nurAktuellerName && !aktiv ? label : undefined}
                  aria-label={nurAktuellerName && !aktiv ? label : undefined}
                  aria-current={aktiv ? "step" : undefined}
                  className={`group shrink-0 inline-flex items-center gap-2.5 select-none ${klickbar ? "cursor-pointer" : "cursor-default"} ${tot ? "opacity-50" : ""}`}
                >
                  <span
                    className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-semibold transition-colors outline-2 outline-offset-2 outline-transparent ${
                      klickbar ? "group-hover:outline-kb" : ""
                    } ${
                      aktiv ? "bg-kb text-white"
                        : weg ? "bg-surface-dim text-muted-soft"
                        : erledigt ? "bg-kb/15 text-kb"
                        : "bg-background text-muted-soft ring-[1.5px] ring-inset ring-border"
                    }`}
                  >
                    {weg ? "–" : erledigt ? (
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : i + 1}
                  </span>
                  {(!nurAktuellerName || aktiv) && (
                    <span className={`text-sm whitespace-nowrap ${weg ? "line-through" : ""} ${
                      aktiv ? "font-semibold text-kb" : erledigt ? "font-medium text-foreground-soft" : "font-medium text-muted-soft"
                    }`}>
                      {label}
                    </span>
                  )}
                </Huelle>
                {i < labels.length - 1 && (
                  <span aria-hidden="true" className={`flex-1 min-w-5 h-0.5 rounded-full ${erledigt ? "bg-kb/40" : "bg-border-soft"}`} />
                )}
              </li>
            );
          })}
        </ol>
      </nav>
    </>
  );
}
