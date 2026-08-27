"use client";

import { Check } from "@phosphor-icons/react";

/** Checkbox in the AIA look so every checkbox in the app looks alike. */
export default function Checkbox({
  checked,
  onChange,
  disabled = false,
  label,
  className = "",
  labelClassName = "text-xs text-foreground",
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  className?: string;
  labelClassName?: string;
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
        <span className={`whitespace-nowrap ${labelClassName}`}>{label}</span>
      )}
    </button>
  );
}
