"use client";

import { useTranslations } from "next-intl";
import { STEPS, type Step } from "../_types";

interface PodcastStepperProps {
  step: Step;
  canEnter: (index: number) => boolean;
  onStepClick: (index: number) => void;
}

/** The same circles and lines as the screencast, only five of them and without the drag. */
export default function PodcastStepper({ step, canEnter, onStepClick }: PodcastStepperProps) {
  const t = useTranslations("tools.podcast.steps");
  const tStepper = useTranslations("stepper");
  const currentIdx = STEPS.indexOf(step);

  return (
    <nav aria-label={tStepper("ariaLabel")} className="mb-10 overflow-x-auto scrollbar-hide">
      <ol className="flex items-center gap-1 sm:gap-2 w-max sm:w-full">
        {STEPS.map((key, i) => {
          const isDone = i < currentIdx;
          const isActive = i === currentIdx;
          const isClickable = canEnter(i);
          const Huelle = isClickable ? "button" : "span";
          return (
            <li key={key} data-active={isActive} className="flex items-center gap-1 sm:gap-2">
              <Huelle
                {...(isClickable ? { type: "button" as const, onClick: () => onStepClick(i) } : {})}
                className={`
                  inline-flex items-center gap-1 sm:gap-1.5 rounded-sm px-1 py-0.5 transition-colors select-none
                  ${isClickable ? "group cursor-pointer" : "cursor-default"}
                `}
              >
                <span
                  className={`
                    inline-flex items-center justify-center w-6 h-6 sm:w-7 sm:h-7 rounded-full text-3xs sm:text-xs font-medium transition-colors flex-shrink-0
                    ${isClickable ? "outline-2 outline-transparent group-hover:outline-kb" : ""}
                    ${isActive ? "bg-kb text-white" : ""}
                    ${isDone ? "bg-kb/20 text-kb" : ""}
                    ${!isActive && !isDone ? "bg-surface text-muted-soft" : ""}
                  `}
                  aria-current={isActive ? "step" : undefined}
                >
                  {isDone ? (
                    <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </span>
                <span
                  className={`text-3xs sm:text-xs whitespace-nowrap ${
                    isActive ? "text-foreground font-medium" : isClickable ? "text-kb" : "text-muted-soft"
                  }`}
                >
                  {t(key)}
                </span>
              </Huelle>
              {i < STEPS.length - 1 && (
                <span className={`w-3 sm:w-8 h-px flex-shrink-0 ${i < currentIdx ? "bg-kb" : "bg-surface-dim"}`} aria-hidden="true" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
