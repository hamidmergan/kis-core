"use client";

import { Check, Minus } from "@phosphor-icons/react";

/** Checkbox in the AIA look so every checkbox in the app looks alike. */
export default function Checkbox({
  checked,
  onChange,
  indeterminate = false,
  disabled = false,
  label,
  className = "",
  labelClassName = "text-xs text-foreground",
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Half state for a box that stands for several others, only some of which are set. */
  indeterminate?: boolean;
  disabled?: boolean;
  label?: string;
  className?: string;
  labelClassName?: string;
}) {
  const boxCls = checked || indeterminate
    ? "border-[var(--kb)] bg-[var(--kb)]"
    : disabled
      ? "border-[var(--border)] bg-background"
      : "border-[var(--border)] bg-background group-hover:border-[var(--kb)]";

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? "mixed" : checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`group flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      <span
        className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${boxCls}`}
        style={{ color: "#fff" }}
      >
        {checked ? <Check size={11} weight="bold" /> : indeterminate && <Minus size={11} weight="bold" />}
      </span>
      {label && (
        <span className={`whitespace-nowrap ${labelClassName}`}>{label}</span>
      )}
    </button>
  );
}
