"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/** Help bubble on click, in a portal so it is not clipped. */
export default function HelpTooltip({ text, image }: { text: string; image?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      if (wrapperRef.current?.contains(target)) return;
      if (tooltipRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    function update() {
      const btn = wrapperRef.current?.getBoundingClientRect();
      if (!btn) return;
      setPos({ top: btn.bottom + 6, left: btn.left + btn.width / 2 });
    }
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open]);

  return (
    <span ref={wrapperRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-3.5 h-3.5 flex items-center justify-center text-[var(--muted)] hover:text-[var(--kb)] transition-colors"
      >
        <svg
          className="w-3.5 h-3.5"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <circle cx="8" cy="8" r="6.5" />
          <path d="M6 6.5a2 2 0 1 1 2.5 1.94V9.5" strokeLinecap="round" />
          <circle cx="8.25" cy="11.5" r="0.5" fill="currentColor" stroke="none" />
        </svg>
      </button>
      {open && pos && typeof document !== "undefined" &&
        createPortal(
          <div
            ref={tooltipRef}
            className="fixed z-50 w-56 -translate-x-1/2 rounded-lg p-2.5 text-xs leading-relaxed shadow-lg text-center whitespace-normal break-words"
            style={{
              top: pos.top,
              left: pos.left,
              backgroundColor: "var(--surface)",
              color: "var(--foreground)",
              border: "1px solid var(--border)",
            }}
          >
            {image && <div className="mb-2">{image}</div>}
            {text}
          </div>,
          document.body,
        )}
    </span>
  );
}
