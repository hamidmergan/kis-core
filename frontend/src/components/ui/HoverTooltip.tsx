"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/** Bubble without a delay as a replacement for title, in a portal and without a box of its own. */
const TOOLTIP_WIDTH = 240; // max width, the box hugs shorter text
const EDGE_MARGIN = 8;

export default function HoverTooltip({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  const [pos, setPos] = useState<{ top: number; left: number; above: boolean } | null>(null);
  const wrapperRef = useRef<HTMLSpanElement>(null);

  const show = useCallback(() => {
    const anchor = wrapperRef.current?.firstElementChild;
    if (!anchor) return;
    const r = anchor.getBoundingClientRect();
    const above = r.bottom + 140 > window.innerHeight;
    // At the window edge the centre moves inwards instead of overflowing.
    const half = TOOLTIP_WIDTH / 2;
    const left = Math.min(
      Math.max(r.left + r.width / 2, half + EDGE_MARGIN),
      window.innerWidth - half - EDGE_MARGIN,
    );
    setPos({ top: above ? r.top - 6 : r.bottom + 6, left, above });
  }, []);

  const hide = useCallback(() => setPos(null), []);

  useEffect(() => {
    if (!pos) return;
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [pos, hide]);

  return (
    <span
      ref={wrapperRef}
      className="contents"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {pos && typeof document !== "undefined" &&
        createPortal(
          <div
            role="tooltip"
            className="fixed z-50 w-max rounded-md px-2 py-1 text-2xs leading-snug shadow-md text-center whitespace-pre-line break-words pointer-events-none"
            style={{
              top: pos.top,
              left: pos.left,
              maxWidth: TOOLTIP_WIDTH,
              transform: pos.above ? "translate(-50%, -100%)" : "translateX(-50%)",
              backgroundColor: "var(--surface)",
              color: "var(--foreground)",
              border: "1px solid var(--border)",
            }}
          >
            {text}
          </div>,
          document.body,
        )}
    </span>
  );
}
