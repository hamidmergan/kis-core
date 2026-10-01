"use client";

import { CaretLeft, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { STEPS, type Step } from "../_types";

interface PraesentationStepperProps {
  step: Step;
  canEnter: (index: number) => boolean;
  /** A step that can never be entered again, shown faded. */
  isClosedForGood: (index: number) => boolean;
  onStepClick: (index: number) => void;
  /** Discards the whole run, absent where there is nothing to discard. */
  onDiscard?: (() => void) | null;
}

/** Numbered underline tabs on the desktop, a back arrow with a progress bar on the phone. */
export default function PraesentationStepper({ step, canEnter, isClosedForGood, onStepClick, onDiscard }: PraesentationStepperProps) {
  const t = useTranslations("tools.praesentation.steps");
  const tPage = useTranslations("tools.praesentation");
  const tCommon = useTranslations("tools.praesentation.common");
  const tStepper = useTranslations("stepper");
  const aktuell = STEPS.indexOf(step);
  const zurueck = aktuell > 0 && canEnter(aktuell - 1) ? aktuell - 1 : null;

  return (
    <>
      <div className="sm:hidden -mx-4 -mt-6 mb-5">
        <div className="h-14 flex items-center gap-3 px-4">
          {zurueck !== null ? (
            <button type="button" onClick={() => onStepClick(zurueck)} aria-label={tCommon("back")} className="text-muted hover:text-kb transition-colors">
              <CaretLeft size={20} weight="bold" />
            </button>
          ) : (
            <Link href="/" aria-label={tCommon("back")} className="text-muted hover:text-kb transition-colors">
              <CaretLeft size={20} weight="bold" />
            </Link>
          )}
          <h1 className="text-base font-bold flex-1">{t(step)}</h1>
          {onDiscard && (
            <button type="button" onClick={onDiscard} aria-label={tPage("discard")} className="text-muted-soft hover:text-error transition-colors">
              <Trash size={18} />
            </button>
          )}
        </div>
        <div className="h-1 bg-border-soft">
          <div className="h-1 bg-kb transition-all" style={{ width: `${((aktuell + 1) / STEPS.length) * 100}%` }} />
        </div>
      </div>

      <nav aria-label={tStepper("ariaLabel")} className="hidden sm:flex justify-center gap-8 border-b border-border-soft mb-8">
        {STEPS.map((key, i) => {
          const aktiv = i === aktuell;
          const klickbar = !aktiv && canEnter(i);
          return (
            <button
              key={key}
              type="button"
              disabled={!klickbar && !aktiv}
              onClick={() => klickbar && onStepClick(i)}
              aria-current={aktiv ? "step" : undefined}
              className={`text-sm pb-3 -mb-px border-b-2 transition-colors ${
                aktiv
                  ? "font-semibold text-kb border-kb cursor-default"
                  : klickbar
                    ? "text-muted border-transparent hover:text-kb"
                    : `text-muted-soft border-transparent cursor-not-allowed ${isClosedForGood(i) ? "opacity-50" : ""}`
              }`}
            >
              {i + 1}&nbsp;&nbsp;{t(key)}
            </button>
          );
        })}
      </nav>
    </>
  );
}
