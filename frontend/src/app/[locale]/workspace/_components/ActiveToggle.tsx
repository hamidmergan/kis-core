"use client";

import { useTranslations } from "next-intl";

interface ActiveToggleProps {
  active: boolean;
  disabled?: boolean;
  onToggle: (newVal: boolean) => void;
  /** Other words for the same switch, a page in Pages is shared or private. */
  labels?: { on: string; off: string; turnOn: string; turnOff: string };
}

/** The active switch of a module, shared by the module list, the sharing window and Pages. */
export default function ActiveToggle({ active, disabled, onToggle, labels }: ActiveToggleProps) {
  const t = useTranslations("workspace.list");

  return (
    <div className="flex items-center gap-2.5">
      <button
        type="button"
        role="switch"
        aria-checked={active}
        aria-label={active
          ? labels?.turnOff ?? t("deactivate", { label: "Workspace" })
          : labels?.turnOn ?? t("activate", { label: "Workspace" })}
        onClick={(e) => { e.stopPropagation(); onToggle(!active); }}
        disabled={disabled}
        className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full border-2 border-transparent transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2 enabled:hover:border-kb"
        style={{ backgroundColor: active ? "var(--kb)" : "var(--border)" }}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
            active ? "translate-x-[1.125rem]" : "translate-x-0.5"
          }`}
        />
      </button>
      <span className="text-xs font-medium" style={{ color: active ? "var(--kb)" : "var(--muted)" }}>
        {active ? labels?.on ?? t("active") : labels?.off ?? t("inactive")}
      </span>
    </div>
  );
}
