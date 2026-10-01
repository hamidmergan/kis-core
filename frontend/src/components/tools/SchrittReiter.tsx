"use client";

import { CaretLeft, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";
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

/** Numbered tabs on the left as in image and translation on the desktop, a back arrow with a progress bar on the phone, shared by the multi-step tools. */
export default function SchrittReiter({ labels, current, canEnter, isClosedForGood, isSkipped, onStepClick, backIndex, onDiscard, discardLabel }: SchrittReiterProps) {
  const t = useTranslations("stepper");
  const tCommon = useTranslations("common");
  const leiste = useRef<HTMLOListElement>(null);
  let zurueck: number | null = null;
  if (backIndex !== undefined) zurueck = backIndex;
  else for (let i = current - 1; i >= 0; i--) if (canEnter(i)) { zurueck = i; break; }

  // With many steps the row scrolls sideways, the current one stays in view.
  useEffect(() => {
    const box = leiste.current;
    const el = box?.children[current] as HTMLElement | undefined;
    if (box && el && box.scrollWidth > box.clientWidth) {
      box.scrollTo({ left: el.offsetLeft - box.clientWidth / 2 + el.clientWidth / 2, behavior: "smooth" });
    }
  }, [current]);

  return (
    <>
      <div className="sm:hidden -mx-4 -mt-6 mb-5">
        <div className="h-14 flex items-center gap-3 px-4">
          {zurueck !== null ? (
            <button type="button" onClick={() => onStepClick(zurueck)} aria-label={t("back")} className="text-muted hover:text-kb transition-colors">
              <CaretLeft size={20} weight="bold" />
            </button>
          ) : (
            <Link href="/" aria-label={tCommon("backToOverview")} className="text-muted hover:text-kb transition-colors">
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

      {/* Same look as the underline Tabs of image and translation, aligned left under the title. */}
      <nav aria-label={t("ariaLabel")} className="hidden sm:block mb-8">
        <ol ref={leiste} className="flex items-end gap-1 overflow-x-auto scrollbar-hide shadow-[inset_0_-1px_0_var(--border)]">
          {labels.map((label, i) => {
            const aktiv = i === current;
            const klickbar = !aktiv && canEnter(i);
            const tot = !aktiv && !klickbar && !!isClosedForGood?.(i);
            const weg = !!isSkipped?.(i);
            return (
              <li key={i} className="shrink-0">
                <button
                  type="button"
                  disabled={!klickbar && !aktiv}
                  onClick={() => klickbar && onStepClick(i)}
                  aria-current={aktiv ? "step" : undefined}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors inline-flex items-center gap-2 whitespace-nowrap rounded-t-md ${
                    aktiv
                      ? "bg-kb/10 text-kb cursor-default"
                      : klickbar
                        ? "text-muted hover:bg-surface hover:text-foreground"
                        : `text-muted cursor-not-allowed ${tot ? "opacity-40" : "opacity-60"}`
                  }`}
                  style={{ borderBottom: `2px solid ${aktiv ? "var(--kb)" : "transparent"}` }}
                >
                  <span className="tabular-nums opacity-70">{i + 1}</span>
                  <span className={weg ? "line-through" : ""}>{label}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
    </>
  );
}
