"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/** Bubble without a delay as a replacement for title, in a portal and without a box of its own. */
const TOOLTIP_WIDTH = 240; // max width, the box hugs shorter text
const EDGE_MARGIN = 8;

export default function HoverTooltip({
  text,
  children,
  tapToOpen = false,
}: {
  text: string;
  children: React.ReactNode;
  /** Touch has no hover, so a tap toggles the bubble instead of selecting the text underneath. */
  tapToOpen?: boolean;
}) {
  const [pos, setPos] = useState<{ top: number; left: number; above: boolean } | null>(null);
  const wrapperRef = useRef<HTMLSpanElement>(null);

  const computePos = useCallback(() => {
    const anchor = wrapperRef.current?.firstElementChild;
    if (!anchor) return null;
    const r = anchor.getBoundingClientRect();
    const above = r.bottom + 140 > window.innerHeight;
    // At the window edge the centre moves inwards instead of overflowing.
    const half = TOOLTIP_WIDTH / 2;
    const left = Math.min(
      Math.max(r.left + r.width / 2, half + EDGE_MARGIN),
      window.innerWidth - half - EDGE_MARGIN,
    );
    return { top: above ? r.top - 6 : r.bottom + 6, left, above };
  }, []);

  const show = useCallback(() => setPos(computePos()), [computePos]);
  const hide = useCallback(() => setPos(null), []);

  const toggle = useCallback(
    (e: React.MouseEvent) => {
      if (!tapToOpen) return;
      e.preventDefault();
      setPos((p) => (p ? null : computePos()));
    },
    [tapToOpen, computePos],
  );

  useEffect(() => {
    if (!pos) return;
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [pos, hide]);

  // A tap opens the bubble, the next tap anywhere else closes it again.
  useEffect(() => {
    if (!tapToOpen || !pos) return;
    function handleOutside(e: MouseEvent) {
      if (wrapperRef.current?.contains(e.target as Node)) return;
      hide();
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [tapToOpen, pos, hide]);

  return (
    <span
      ref={wrapperRef}
      className={tapToOpen ? "contents select-none [-webkit-touch-callout:none]" : "contents"}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      onClick={toggle}
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
