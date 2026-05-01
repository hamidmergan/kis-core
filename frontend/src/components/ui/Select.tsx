"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CaretDown, Check } from "@phosphor-icons/react";

export interface SelectOption<T extends string> {
  value: T;
  label: ReactNode;
  disabled?: boolean;
}

interface SelectProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: ReadonlyArray<SelectOption<T>>;
  disabled?: boolean;
  placeholder?: string;
  id?: string;
  className?: string;
}

export default function Select<T extends string>({
  value,
  onChange,
  options,
  disabled = false,
  placeholder = "Bitte wählen",
  id,
  className = "",
}: SelectProps<T>) {
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState<number>(-1);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selectedIdx = options.findIndex((o) => o.value === value);
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
      setPos({ top: r.bottom + 4, left: r.left, width: r.width });
    }
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open]);

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
    <div ref={rootRef} className={`relative ${className}`} onKeyDown={onKeyDown}>
      <button
        ref={buttonRef}
        id={id}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        className="group block w-full rounded-md border-2 border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm hover:border-kb focus:border-kb focus:outline-none focus:ring-1 focus:ring-kb disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-border transition-colors flex items-center justify-between gap-2 text-left"
      >
        <span className={`flex-1 truncate ${selected ? "" : "text-muted-soft"}`}>
          {selected ? selected.label : placeholder}
        </span>
        <CaretDown
          size={14}
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
            width: pos.width,
            backgroundColor: "#fff",
            border: "1px solid var(--border)",
            boxShadow: "0 8px 24px rgba(0,40,60,0.12)",
          }}
        >
          {options.map((opt, idx) => {
            const isSelected = idx === selectedIdx;
            const isHighlighted = idx === highlightIdx;
            return (
              <li
                key={opt.value}
                role="option"
                aria-selected={isSelected}
                aria-disabled={opt.disabled}
                onMouseEnter={() => !opt.disabled && setHighlightIdx(idx)}
                onMouseDown={(e) => { e.preventDefault(); commit(idx); }}
                className={`px-3 py-1.5 flex items-center gap-2 ${opt.disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
                style={{
                  backgroundColor: isHighlighted && !opt.disabled ? "var(--surface)" : "transparent",
                  color: "var(--foreground)",
                  fontWeight: isSelected ? 600 : 400,
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
