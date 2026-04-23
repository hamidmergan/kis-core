"use client";

import { useCallback, useEffect, useRef } from "react";
import type { ScreencastStep } from "@/types";
import { STEP_LABELS, stepToIndex } from "./steps";

interface ScreencastStepperProps {
  step: ScreencastStep;
  maxReachedIdx: number;
  sourceLang: string;
  onStepClick: (index: number) => void;
}

export default function ScreencastStepper({
  step,
  maxReachedIdx,
  sourceLang,
  onStepClick,
}: ScreencastStepperProps) {
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
      aria-label="Fortschritt"
      className="mb-6 overflow-x-auto scrollbar-hide cursor-grab touch-pan-x"
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      <ol className="flex items-center gap-1 sm:gap-2 min-w-0 w-max sm:w-full">
        {STEP_LABELS.map((label, i) => {
          const isSkipped = sourceLang === "EN" && (i === 1 || i === 2);
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
            <li key={label} data-active={isActive} className="flex items-center gap-1 sm:gap-2">
              <button
                type="button"
                onClick={() => handleClick(i)}
                aria-disabled={!isClickable}
                className={`
                  inline-flex items-center gap-1 sm:gap-1.5 rounded-sm px-1 py-0.5 transition-colors select-none
                  ${isClickable ? "cursor-pointer hover:bg-gray-100" : "cursor-default"}
                `}
              >
                <span
                  className={`
                    inline-flex items-center justify-center w-6 h-6 sm:w-7 sm:h-7 rounded-full text-[10px] sm:text-xs font-medium transition-colors flex-shrink-0
                    ${isActive ? "bg-primary text-white" : ""}
                    ${isDone ? "bg-primary/20 text-primary" : ""}
                    ${isSkipped ? "bg-gray-100 text-gray-300" : ""}
                    ${!isActive && !isDone && !isSkipped ? "bg-gray-100 text-gray-400" : ""}
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
                      ? "text-gray-300 line-through"
                      : isActive
                        ? "text-gray-900 font-medium"
                        : isClickable
                          ? "text-gray-600"
                          : "text-gray-400"
                  }`}
                >
                  {label}
                </span>
              </button>
              {i < STEP_LABELS.length - 1 && (
                <span
                  className={`w-3 sm:w-8 h-px flex-shrink-0 ${
                    i < currentIdx && !isSkipped ? "bg-primary" : "bg-gray-200"
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
