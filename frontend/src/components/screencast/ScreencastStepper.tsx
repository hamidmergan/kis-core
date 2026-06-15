"use client";

import { useCallback, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import type { ScreencastStep } from "@/types";
import { STEP_KEYS, stepToIndex } from "./steps";

interface ScreencastStepperProps {
  step: ScreencastStep;
  maxReachedIdx: number;
  skipTranslation: boolean;
  onStepClick: (index: number) => void;
}

export default function ScreencastStepper({
  step,
  maxReachedIdx,
  skipTranslation,
  onStepClick,
}: ScreencastStepperProps) {
  const t = useTranslations("stepper");
  const containerRef = useRef<HTMLElement>(null);
  const isDraggingRef = useRef(false);
  const hasDraggedRef = useRef(false);
  const dragStartXRef = useRef(0);
  const dragScrollLeftRef = useRef(0);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    const el = containerRef.current;
    if (!el) return;
    isDraggingRef.current = true;
    hasDraggedRef.current = false;
    dragStartXRef.current = e.pageX - el.offsetLeft;
    dragScrollLeftRef.current = el.scrollLeft;
    el.style.cursor = "grabbing";
    el.style.userSelect = "none";
  }, []);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    e.preventDefault();
    const el = containerRef.current;
    if (!el) return;
    const x = e.pageX - el.offsetLeft;
    if (Math.abs(x - dragStartXRef.current) > 5) {
      hasDraggedRef.current = true;
    }
    const walk = (x - dragStartXRef.current) * 1.5;
    el.scrollLeft = dragScrollLeftRef.current - walk;
  }, []);

  const onMouseUp = useCallback(() => {
    isDraggingRef.current = false;
    const el = containerRef.current;
    if (el) {
      el.style.cursor = "";
      el.style.userSelect = "";
    }
  }, []);

  const handleClick = useCallback(
    (index: number) => {
      if (hasDraggedRef.current) return;
      onStepClick(index);
    },
    [onStepClick],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const activeEl = container.querySelector<HTMLElement>('[data-active="true"]');
    if (!activeEl) return;
    const containerRect = container.getBoundingClientRect();
    const activeRect = activeEl.getBoundingClientRect();
    const offset =
      activeRect.left -
      containerRect.left -
      containerRect.width / 2 +
      activeRect.width / 2;
    container.scrollBy({ left: offset, behavior: "smooth" });
  }, [step]);

  const currentIdx = stepToIndex(step);

  return (
    <nav
      ref={containerRef}
      aria-label={t("ariaLabel")}
      className="mb-6 overflow-x-auto scrollbar-hide cursor-grab touch-pan-x"
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      <ol className="flex items-center gap-1 sm:gap-2 min-w-0 w-max sm:w-full">
        {STEP_KEYS.map((stepKey, i) => {
          const label = t(`steps.${stepKey}`);
          const isSkipped = skipTranslation && (i === 1 || i === 2);
          const isDone = !isSkipped && i < currentIdx;
          const isActive = i === currentIdx;
          const isReached = i <= maxReachedIdx;
          const isClickable =
            !isSkipped &&
            isReached &&
            !isActive &&
            i !== 0 &&
            i !== 1 &&
            i !== 6 &&
            step !== "rendering";
          return (
            <li key={stepKey} data-active={isActive} className="flex items-center gap-1 sm:gap-2">
              <button
                type="button"
                onClick={() => handleClick(i)}
                aria-disabled={!isClickable}
                className={`
                  inline-flex items-center gap-1 sm:gap-1.5 rounded-sm px-1 py-0.5 transition-colors select-none
                  ${isClickable ? "cursor-pointer hover:bg-surface" : "cursor-default"}
                `}
              >
                <span
                  className={`
                    inline-flex items-center justify-center w-6 h-6 sm:w-7 sm:h-7 rounded-full text-[10px] sm:text-xs font-medium transition-colors flex-shrink-0
                    ${isActive ? "bg-kb text-white" : ""}
                    ${isDone ? "bg-kb/20 text-kb" : ""}
                    ${isSkipped ? "bg-surface text-border" : ""}
                    ${!isActive && !isDone && !isSkipped ? "bg-surface text-muted-soft" : ""}
                  `}
                  aria-current={isActive ? "step" : undefined}
                >
                  {isSkipped ? (
                    <svg
                      className="w-3 h-3 sm:w-3.5 sm:h-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 12h12" />
                    </svg>
                  ) : isDone ? (
                    <svg
                      className="w-3 h-3 sm:w-4 sm:h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </span>
                <span
                  className={`text-[10px] sm:text-xs whitespace-nowrap ${
                    isSkipped
                      ? "text-border line-through"
                      : isActive
                        ? "text-foreground font-medium"
                        : isClickable
                          ? "text-foreground-soft"
                          : "text-muted-soft"
                  }`}
                >
                  {label}
                </span>
              </button>
              {i < STEP_KEYS.length - 1 && (
                <span
                  className={`w-3 sm:w-8 h-px flex-shrink-0 ${
                    i < currentIdx && !isSkipped ? "bg-kb" : "bg-surface-dim"
                  }`}
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
