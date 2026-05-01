"use client";

import { useEffect, useRef, useState } from "react";
import { CaretDown, Check, Globe } from "@phosphor-icons/react";

type Lang = "de" | "en";

const OPTIONS: { value: Lang; label: string }[] = [
  { value: "de", label: "Deutsch" },
  { value: "en", label: "English" },
];

export default function HeaderLanguageSwitch() {
  const [value, setValue] = useState<Lang>("de");
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const selectedIdx = OPTIONS.findIndex((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  useEffect(() => {
    if (open) setHighlightIdx(selectedIdx >= 0 ? selectedIdx : 0);
  }, [open, selectedIdx]);

  const commit = (idx: number) => {
    const opt = OPTIONS[idx];
    if (!opt) return;
    setValue(opt.value);
    setOpen(false);
    buttonRef.current?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (e.key === "Escape") { e.preventDefault(); setOpen(false); buttonRef.current?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setHighlightIdx((i) => (i + 1) % OPTIONS.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHighlightIdx((i) => (i - 1 + OPTIONS.length) % OPTIONS.length); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); commit(highlightIdx); }
    else if (e.key === "Tab") { setOpen(false); }
  };

  return (
    <div ref={rootRef} className="relative" onKeyDown={onKeyDown}>
      <button
        ref={buttonRef}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label="Sprache wählen"
        title="Sprache"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-center w-10 h-10 sm:w-auto sm:h-9 sm:px-3 sm:gap-1.5 rounded-full btn-on-dark"
      >
        <Globe size={17} weight="bold" aria-hidden="true" />
        <span className="hidden sm:inline text-sm font-medium uppercase">{value}</span>
        <CaretDown
          size={12}
          weight="bold"
          aria-hidden="true"
          className={`hidden sm:inline transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute right-0 top-full mt-2 z-50 min-w-[160px] rounded-xl py-1 text-sm"
          style={{
            backgroundColor: "var(--background)",
            border: "1px solid var(--border)",
            boxShadow: "0 8px 24px rgba(0,40,60,0.12)",
          }}
        >
          {OPTIONS.map((opt, idx) => {
            const isSelected = idx === selectedIdx;
            const isHighlighted = idx === highlightIdx;
            return (
              <li
                key={opt.value}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setHighlightIdx(idx)}
                onMouseDown={(e) => { e.preventDefault(); commit(idx); }}
                className="px-3 py-2 flex items-center gap-2 cursor-pointer"
                style={{
                  backgroundColor: isHighlighted ? "var(--surface)" : "transparent",
                  color: "var(--foreground)",
                  fontWeight: isSelected ? 600 : 400,
                }}
              >
                <span className="text-xs uppercase font-mono w-6" style={{ color: "var(--muted)" }}>
                  {opt.value}
                </span>
                <span className="flex-1">{opt.label}</span>
                {isSelected && <Check size={14} weight="bold" style={{ color: "var(--kb)" }} />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
