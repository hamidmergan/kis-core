"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { createPortal } from "react-dom";
import { CaretDown, Check } from "@phosphor-icons/react";

export interface SelectOption<T extends string> {
  value: T;
  label: ReactNode;
  disabled?: boolean;
  /** "action" opens something instead of picking a value: set off, dashed, never ticked. */
  variant?: "action";
}

interface SelectProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: ReadonlyArray<SelectOption<T>>;
  disabled?: boolean;
  placeholder?: string;
  id?: string;
  /** For a select that stands without a visible label of its own. */
  ariaLabel?: string;
  className?: string;
  // 'md' is the wide form control, 'sm' the narrow pill for toolbars.
  size?: "sm" | "md";
}

// "sm" pill popover sizing configuration (expressed once, derived for both arithmetic and CSS)
const SM_POPOVER_MAX_WIDTH_PX = 256; // 16rem at 16px font base
const SM_POPOVER_MAX_WIDTH_REM = `${SM_POPOVER_MAX_WIDTH_PX / 16}rem`; // "16rem"
const SM_POPOVER_MARGIN_PX = 8;

// Conflicting classes are decided by stylesheet order, hence separate lists.
const SIZE_CLS = {
  md: "block w-full rounded-md px-3 py-2 text-sm gap-2",
  sm: "rounded-full px-2.5 py-1 text-xs gap-1.5 max-w-[16rem]",
} as const;

const BUTTON_BASE =
  "group border-2 border-border bg-background text-foreground shadow-sm hover:border-kb "
  + "focus:border-kb focus:outline-none focus:ring-1 focus:ring-kb disabled:opacity-50 "
  + "disabled:cursor-not-allowed disabled:hover:border-border transition-colors "
  + "flex items-center justify-between text-left";

export default function Select<T extends string>({
  value,
  onChange,
  options,
  disabled = false,
  placeholder,
  id,
  ariaLabel,
  className = "",
  size = "md",
}: SelectProps<T>) {
  const t = useTranslations("common");
  const resolvedPlaceholder = placeholder ?? t("pleaseSelect");
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState<number>(-1);
  const [pos, setPos] = useState<{ top: number; left: number; width: number; smMaxWidth?: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // An action entry is no choice, so it never counts as the selected one.
  const selectedIdx = options.findIndex((o) => o.value === value && o.variant !== "action");
  const selected = options[selectedIdx];

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as Node;
      if (rootRef.current?.contains(target)) return;
      if (listRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    function update() {
      const r = buttonRef.current?.getBoundingClientRect();
      if (!r) return;

      if (size === "sm") {
        // 'sm' stays anchored under the button and is only bounded in width.
        const left = r.left;
        const availableWidth = window.innerWidth - left - SM_POPOVER_MARGIN_PX;
        const smMaxWidth = Math.min(SM_POPOVER_MAX_WIDTH_PX, Math.max(r.width, availableWidth));
        setPos({ top: r.bottom + 4, left, width: r.width, smMaxWidth });
      } else {
        // "md" unchanged: no clamping, popover width pinned to button width
        setPos({ top: r.bottom + 4, left: r.left, width: r.width });
      }
    }
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open, size]);

  useEffect(() => {
    if (open) setHighlightIdx(selectedIdx >= 0 ? selectedIdx : 0);
  }, [open, selectedIdx]);

  useEffect(() => {
    if (!open || highlightIdx < 0) return;
    const el = listRef.current?.children[highlightIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [open, highlightIdx]);

  function move(delta: number) {
    setHighlightIdx((curr) => {
      const n = options.length;
      let next = curr;
      for (let i = 0; i < n; i++) {
        next = (next + delta + n) % n;
        if (!options[next].disabled) return next;
      }
      return curr;
    });
  }

  function commit(idx: number) {
    const opt = options[idx];
    if (!opt || opt.disabled) return;
    onChange(opt.value);
    setOpen(false);
    buttonRef.current?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (disabled) return;
    if (!open) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (e.key === "Escape") { e.preventDefault(); setOpen(false); buttonRef.current?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    else if (e.key === "Home") { e.preventDefault(); setHighlightIdx(0); }
    else if (e.key === "End") { e.preventDefault(); setHighlightIdx(options.length - 1); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); commit(highlightIdx); }
    else if (e.key === "Tab") { setOpen(false); }
  }

  return (
    <div ref={rootRef} className={`relative ${size === "sm" ? "w-fit" : ""} ${className}`} onKeyDown={onKeyDown}>
      <button
        ref={buttonRef}
        id={id}
        type="button"
        role="combobox"
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        className={`${BUTTON_BASE} ${SIZE_CLS[size]}`}
      >
        <span className={`flex-1 truncate ${selected ? "" : "text-muted-soft"}`}>
          {selected ? selected.label : resolvedPlaceholder}
        </span>
        <CaretDown
          size={size === "sm" ? 12 : 14}
          weight="bold"
          className={`flex-shrink-0 transition-transform text-muted group-hover:text-kb group-focus:text-kb ${open ? "rotate-180 text-kb" : ""}`}
        />
      </button>
      {open && pos && typeof document !== "undefined" && createPortal(
        <ul
          ref={listRef}
          role="listbox"
          className="fixed z-[100] max-h-60 overflow-y-auto rounded-md py-1 text-sm"
          style={{
            top: pos.top,
            left: pos.left,
            // 'sm' may grow past the button, 'md' stays at the field width.
            ...(size === "sm"
              ? { minWidth: pos.width, width: "max-content", maxWidth: pos.smMaxWidth ? `${pos.smMaxWidth}px` : SM_POPOVER_MAX_WIDTH_REM }
              : { width: pos.width }),
            backgroundColor: "var(--background)",
            border: "1px solid var(--border)",
            boxShadow: "0 8px 24px rgba(0,40,60,0.12)",
          }}
        >
          {options.map((opt, idx) => {
            const isSelected = idx === selectedIdx;
            const isHighlighted = idx === highlightIdx;
            const isAction = opt.variant === "action";
            return (
              <li
                key={opt.value}
                role="option"
                aria-selected={isSelected}
                aria-disabled={opt.disabled}
                onMouseEnter={() => !opt.disabled && setHighlightIdx(idx)}
                onMouseDown={(e) => { e.preventDefault(); commit(idx); }}
                className={`px-3 py-1.5 flex items-center gap-2 ${opt.disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"} ${isAction ? "mt-1" : ""}`}
                style={{
                  backgroundColor: isHighlighted && !opt.disabled ? "var(--surface)" : "transparent",
                  color: isAction ? "var(--muted)" : "var(--foreground)",
                  fontWeight: isSelected ? 600 : 400,
                  // The dashed line above sets the action off from the real choices.
                  ...(isAction ? { borderTop: "1px dashed var(--border)" } : {}),
                }}
              >
                <span className="flex-1 truncate">{opt.label}</span>
                {isSelected && <Check size={12} weight="bold" style={{ color: "var(--kb)" }} />}
              </li>
            );
          })}
        </ul>,
        document.body,
      )}
    </div>
  );
}
