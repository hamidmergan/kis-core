"use client";

import { CaretLeft, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

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
  /** The phone's back arrow, by default the nearest enterable step to the left or the overview. */
  backIndex?: number | null;
  /** Discards the whole run, absent where there is nothing to discard. */
  onDiscard?: (() => void) | null;
  discardLabel?: string;
}

/** Numbered circles in a light band on the desktop, a back arrow with a progress bar on the phone, shared by the multi-step tools. */
export default function SchrittReiter({ labels, current, canEnter, isClosedForGood, isSkipped, onStepClick, backIndex, onDiscard, discardLabel }: SchrittReiterProps) {
  const t = useTranslations("stepper");
  const tCommon = useTranslations("common");
  let zurueck: number | null = null;
  if (backIndex !== undefined) zurueck = backIndex;
  else for (let i = current - 1; i >= 0; i--) if (canEnter(i)) { zurueck = i; break; }

  // With many steps only the current one keeps its name, the others stay circles with a tooltip.
  const nurAktuellerName = labels.length > 5;

  return (
    <>
      <div className="sm:hidden -mx-4 -mt-6 mb-5">
        <div className="h-14 flex items-center gap-3 px-4">
          {zurueck !== null ? (
            <button type="button" onClick={() => onStepClick(zurueck)} aria-label={t("back")} className="text-muted hover:text-kb transition-colors">
              <CaretLeft size={20} weight="bold" />
            </button>
          ) : (
            <Link href="/" aria-label={tCommon("backToTools")} className="text-muted hover:text-kb transition-colors">
              <CaretLeft size={20} weight="bold" />
            </Link>
          )}
          <h1 className="text-base font-bold flex-1">{labels[current]}</h1>
          {onDiscard && (
            <button type="button" onClick={onDiscard} aria-label={discardLabel} className="text-muted-soft hover:text-error transition-colors">
              <Trash size={18} />
            </button>
          )}
        </div>
        <div className="h-1 bg-border-soft">
          <div className="h-1 bg-kb transition-all" style={{ width: `${((current + 1) / labels.length) * 100}%` }} />
        </div>
      </div>

      <nav aria-label={t("ariaLabel")} className="hidden sm:block mt-6 mb-10">
        <ol className="flex items-center gap-2.5 rounded-2xl border border-border-soft bg-surface px-7 py-5">
          {labels.map((label, i) => {
            const aktiv = i === current;
            const erledigt = i < current;
            const klickbar = !aktiv && canEnter(i);
            const tot = !aktiv && !klickbar && !!isClosedForGood?.(i);
            const weg = !!isSkipped?.(i);
            const Huelle = klickbar ? "button" : "span";
            return (
              <li key={i} className={`flex items-center gap-2.5 ${i < labels.length - 1 ? "flex-1" : ""}`}>
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
                  <span aria-hidden="true" className={`flex-1 min-w-3 h-0.5 rounded-full ${erledigt ? "bg-kb/40" : "bg-border-soft"}`} />
                )}
              </li>
            );
          })}
        </ol>
      </nav>
    </>
  );
}
