"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Check } from "@phosphor-icons/react";
import type { LanguageChoice, Languages } from "../_lib/types";

/** The language the page is shown in as a short round button, the other opens on hover with a mouse and on tap otherwise. */
export function LanguageSwitch({ value, choices, disabled, title, className, onChange }: {
  value: string; choices: LanguageChoice[]; disabled?: boolean; title?: string; className?: string; onChange: (key: string) => void;
}) {
  const t = useTranslations("tools.pages");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  // A click on the button right after the hover opened the menu must not close it again.
  const openedByHover = useRef(false);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent | TouchEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (choices.length < 2) return null;
  const choose = (key: string) => {
    setOpen(false);
    if (key !== value) onChange(key);
  };

  return (
    <div
      ref={rootRef}
      className={`relative ${className ?? ""}`}
      // A disabled button shows no tooltip of its own, so the reason sits on the wrapper.
      title={disabled ? title : undefined}
      // Touch devices send no pointer enter, so a tap falls through to the click below.
      onPointerEnter={(e) => { if (e.pointerType === "mouse" && !disabled) { openedByHover.current = true; setOpen(true); } }}
      onPointerLeave={(e) => { if (e.pointerType === "mouse") { openedByHover.current = false; setOpen(false); } }}
    >
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("languageSelect")}
        title={disabled ? undefined : t("languageSelect")}
        disabled={disabled}
        onClick={() => {
          if (openedByHover.current) { openedByHover.current = false; return; }
          setOpen((v) => !v);
        }}
        className="w-7 h-7 flex items-center justify-center rounded-full btn-icon flex-shrink-0 text-xs font-semibold uppercase disabled:opacity-50 disabled:cursor-not-allowed"
        style={{ backgroundColor: "var(--surface-dim)" }}
      >
        {value}
      </button>
      {open && (
        // The wrapper has no gap to the button, so the pointer never leaves the hover area on the way down.
        <div className="absolute right-0 top-full z-50 pt-1" role="menu" aria-label={t("languageSelect")}>
          <div
            className="w-40 rounded-xl py-1 overflow-hidden"
            style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", boxShadow: "0 8px 24px rgba(0,40,60,0.18)" }}
          >
            {choices.map((c) => {
              const isSelected = c.key === value;
              return (
                <button
                  key={c.key}
                  type="button"
                  role="menuitemradio"
                  aria-checked={isSelected}
                  onClick={() => choose(c.key)}
                  className="flex items-center gap-3 w-full px-4 py-2.5 text-sm font-medium text-left cursor-pointer hover:bg-[var(--surface-dim)] focus:bg-[var(--surface-dim)] outline-none"
                  style={{ color: "var(--foreground)" }}
                >
                  <span className="text-xs uppercase font-mono w-5" style={{ color: "var(--muted)" }} aria-hidden="true">{c.key}</span>
                  <span className="flex-1" style={{ fontWeight: isSelected ? 600 : 400 }}>{c.label}</span>
                  {isSelected && <Check size={14} weight="bold" style={{ color: "var(--kb-dark)" }} aria-hidden="true" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/** The languages of what the owner can read and switch to, the page's own first. */
export function readableOf(l: Languages | null): LanguageChoice[] {
  if (!l) return [];
  return [l.own, ...l.languages.filter((x) => x.state === "done").map(({ key, label }) => ({ key, label }))];
}
