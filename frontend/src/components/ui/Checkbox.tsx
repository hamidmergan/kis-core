"use client";

import { Check } from "@phosphor-icons/react";

/**
 * Kaestchen im AIA-Look: quadratischer Knopf mit 2px-Rahmen, gefuellt in der
 * Akzentfarbe wenn gesetzt. Gleiche Darstellung wie in der Quellenliste und im
 * Lernplan, damit jedes Kaestchen in der App gleich aussieht.
 */
export default function Checkbox({
  checked,
  onChange,
  disabled = false,
  label,
  className = "",
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  className?: string;
}) {
  const boxCls = checked
    ? "border-[var(--kb)] bg-[var(--kb)]"
    : disabled
      ? "border-[var(--border)] bg-background"
      : "border-[var(--border)] bg-background group-hover:border-[var(--kb)]";

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`group flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      <span
        className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${boxCls}`}
        style={{ color: "#fff" }}
      >
        {checked && <Check size={11} weight="bold" />}
      </span>
      {label && (
        <span className="text-xs text-foreground whitespace-nowrap">{label}</span>
      )}
    </button>
  );
}
