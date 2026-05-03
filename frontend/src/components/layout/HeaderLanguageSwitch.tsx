"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CaretDown, Check, Globe } from "@phosphor-icons/react";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { UI_LOCALES } from "@/lib/constants";

const LOCALES = UI_LOCALES as readonly Locale[];

async function persistLocale(locale: Locale) {
  try {
    await fetch("/api/me/locale", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale }),
    });
  } catch {
    // Backend offline / not logged in — cookie + URL still work.
  }
}

export default function HeaderLanguageSwitch() {
  const t = useTranslations("languageSwitch");
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;

  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const closeTimer = useRef<number | null>(null);

  const selectedIdx = LOCALES.findIndex((l) => l === currentLocale);

  const cancelClose = () => {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };
  const scheduleClose = () => {
    cancelClose();
    closeTimer.current = window.setTimeout(() => setOpen(false), 150);
  };

  useEffect(() => () => cancelClose(), []);

  const handlePointerEnter = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse") return;
    cancelClose();
    setOpen(true);
  };
  const handlePointerLeave = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse") return;
    scheduleClose();
  };

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
    const next = LOCALES[idx];
    if (!next) return;
    setOpen(false);
    buttonRef.current?.focus();
    if (next === currentLocale) return;
    router.replace(pathname, { locale: next });
    router.refresh();
    void persistLocale(next);
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
    else if (e.key === "ArrowDown") { e.preventDefault(); setHighlightIdx((i) => (i + 1) % LOCALES.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHighlightIdx((i) => (i - 1 + LOCALES.length) % LOCALES.length); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); commit(highlightIdx); }
    else if (e.key === "Tab") { setOpen(false); }
  };

  return (
    <div
      ref={rootRef}
      className="relative"
      onKeyDown={onKeyDown}
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
    >
      <button
        ref={buttonRef}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={t("ariaLabel")}
        title={t("title")}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-center w-10 h-10 sm:w-auto sm:h-9 sm:px-3 sm:gap-1.5 rounded-full btn-on-dark"
      >
        <Globe size={17} weight="bold" aria-hidden="true" />
        <span className="hidden sm:inline text-sm font-medium uppercase">{currentLocale}</span>
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
          {LOCALES.map((loc, idx) => {
            const isSelected = idx === selectedIdx;
            const isHighlighted = idx === highlightIdx;
            return (
              <li
                key={loc}
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
                  {loc}
                </span>
                <span className="flex-1">{t(loc)}</span>
                {isSelected && <Check size={14} weight="bold" style={{ color: "var(--kb)" }} />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
