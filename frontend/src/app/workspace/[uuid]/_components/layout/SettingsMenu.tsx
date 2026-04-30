"use client";

import React from "react";
import { useHildePref } from "@/hooks/useHildePref";

interface SettingsMenuProps {
  studioEnabled: boolean;
  onToggleStudio: () => void;
  language_trainingActive: boolean;
  onToggleLanguageTraining: () => void;
}

export function SettingsMenu({
  studioEnabled,
  onToggleStudio,
  language_trainingActive,
  onToggleLanguageTraining,
}: SettingsMenuProps) {
  const { enabled: hildeEnabled, toggle: toggleHilde } = useHildePref();

  return (
    <div
      className="absolute right-0 top-10 z-50 rounded-xl shadow-lg"
      style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", width: 260 }}
    >
      <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>Meine Einstellungen</p>
      </div>
      {/* Hilde-Maskottchen (global, alle Workspaces) */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>Hilde-Maskottchen</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>Eulen-Begleiterin im Chat anzeigen</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={hildeEnabled}
          onClick={toggleHilde}
          className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent hover:border-[var(--kb)] transition-colors duration-200"
          style={{ backgroundColor: hildeEnabled ? "var(--kb)" : "var(--border)" }}
        >
          <span
            className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
            style={{ transform: hildeEnabled ? "translateX(16px)" : "translateX(0)" }}
          />
        </button>
      </div>
      {/* Studio-Panel */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>Studio</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>Studio-Panel anzeigen</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={studioEnabled}
          onClick={onToggleStudio}
          className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent hover:border-[var(--kb)] disabled:hover:border-transparent transition-colors duration-200"
          style={{ backgroundColor: studioEnabled ? "var(--kb)" : "var(--border)" }}
        >
          <span
            className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
            style={{ transform: studioEnabled ? "translateX(16px)" : "translateX(0)" }}
          />
        </button>
      </div>
      {/* LanguageTraining */}
      <div className="flex items-center justify-between px-4 py-3" style={{ opacity: studioEnabled ? 1 : 0.4 }}>
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>Fachsprachentraining</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>Zeigt Fachsprachentraining-Tab im Studio</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={language_trainingActive}
          onClick={() => studioEnabled && onToggleLanguageTraining()}
          disabled={!studioEnabled}
          className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent hover:border-[var(--kb)] disabled:hover:border-transparent transition-colors duration-200"
          style={{ backgroundColor: language_trainingActive && studioEnabled ? "var(--kb)" : "var(--border)", cursor: studioEnabled ? "pointer" : "not-allowed" }}
        >
          <span
            className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
            style={{ transform: language_trainingActive && studioEnabled ? "translateX(16px)" : "translateX(0)" }}
          />
        </button>
      </div>
    </div>
  );
}
