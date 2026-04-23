"use client";

import React from "react";

interface SettingsMenuProps {
  chatLang: "de" | "en";
  studioEnabled: boolean;
  onToggleStudio: () => void;
  sprachtrainingActive: boolean;
  onToggleSprachtraining: () => void;
  isLecturer: boolean;
  hideHeader: boolean;
  onToggleHideHeader: () => void;
}

export function SettingsMenu({
  chatLang,
  studioEnabled,
  onToggleStudio,
  sprachtrainingActive,
  onToggleSprachtraining,
  isLecturer,
  hideHeader,
  onToggleHideHeader,
}: SettingsMenuProps) {
  return (
    <div
      className="absolute right-0 top-10 z-50 rounded-xl shadow-lg"
      style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", width: 260 }}
    >
      <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>Meine Einstellungen</p>
      </div>
      {/* Chat-Sprache (disabled – requires full UI + tool language support) */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)", opacity: 0.4 }}>
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Chat-Sprache</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>Sprache der KI-Antworten</p>
        </div>
        <div className="flex gap-1">
          {(["de", "en"] as const).map((lang) => (
            <button
              key={lang}
              type="button"
              disabled
              className="text-xs font-semibold px-2.5 py-1 rounded-lg cursor-not-allowed"
              style={{
                backgroundColor: chatLang === lang ? "var(--kb)" : "var(--border)",
                color: chatLang === lang ? "white" : "var(--muted)",
              }}
            >
              {lang.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      {/* Studio-Panel */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Studio</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>Studio-Panel anzeigen</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={studioEnabled}
          onClick={onToggleStudio}
          className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
          style={{ backgroundColor: studioEnabled ? "var(--kb)" : "#CBD5E1" }}
        >
          <span
            className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
            style={{ transform: studioEnabled ? "translateX(16px)" : "translateX(0)" }}
          />
        </button>
      </div>
      {/* Sprachtraining */}
      <div className="flex items-center justify-between px-4 py-3" style={{ opacity: studioEnabled ? 1 : 0.4 }}>
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Fachsprachentraining</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>Zeigt Fachsprachentraining-Tab im Studio</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={sprachtrainingActive}
          onClick={() => studioEnabled && onToggleSprachtraining()}
          disabled={!studioEnabled}
          className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
          style={{ backgroundColor: sprachtrainingActive && studioEnabled ? "var(--kb)" : "#CBD5E1", cursor: studioEnabled ? "pointer" : "not-allowed" }}
        >
          <span
            className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
            style={{ transform: sprachtrainingActive && studioEnabled ? "translateX(16px)" : "translateX(0)" }}
          />
        </button>
      </div>
      {/* Header ausblenden (nur Ersteller/Lecturer) */}
      {isLecturer && (
        <div className="flex items-center justify-between px-4 py-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Header ausblenden</p>
            <p className="text-xs" style={{ color: "var(--muted)" }}>Nur auf dieser Workspace-Seite</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={hideHeader}
            onClick={onToggleHideHeader}
            className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
            style={{ backgroundColor: hideHeader ? "var(--kb)" : "#CBD5E1" }}
          >
            <span
              className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
              style={{ transform: hideHeader ? "translateX(16px)" : "translateX(0)" }}
            />
          </button>
        </div>
      )}
    </div>
  );
}
