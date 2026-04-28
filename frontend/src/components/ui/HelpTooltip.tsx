"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Click-based help tooltip — click to open, click outside to close.
 * Uses theme CSS variables for consistent styling across the app.
 */
export default function HelpTooltip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <span ref={ref} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-3.5 h-3.5 flex items-center justify-center btn-icon"
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
      {open && (
        <div
          className="absolute left-1/2 -translate-x-1/2 top-full mt-1.5 z-50 w-56 rounded-lg p-2.5 text-xs leading-relaxed shadow-lg text-center whitespace-normal break-words"
          style={{
            backgroundColor: "var(--surface)",
            color: "var(--text)",
            border: "1px solid var(--border)",
          }}
        >
          {text}
        </div>
      )}
    </span>
  );
}
