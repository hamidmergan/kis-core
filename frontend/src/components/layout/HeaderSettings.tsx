"use client";

import { useState } from "react";
import { Gear } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import { useHildePref } from "@/hooks/useHildePref";

export default function HeaderSettings() {
  const [open, setOpen] = useState(false);
  const { enabled: hildeEnabled, toggle: toggleHilde } = useHildePref();

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Einstellungen"
        title="Einstellungen"
        className="flex items-center justify-center w-10 h-10 sm:w-auto sm:h-9 sm:px-3 sm:gap-1.5 rounded-full btn-on-dark"
      >
        <Gear size={17} weight="bold" aria-hidden="true" />
        <span className="hidden sm:inline text-sm font-medium">Einstellungen</span>
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title="Einstellungen" size="md">
        <div className="flex flex-col">
          <div
            className="text-xs font-semibold uppercase tracking-wide mb-3"
            style={{ color: "var(--muted)" }}
          >
            Anzeige
          </div>

          <button
            type="button"
            onClick={toggleHilde}
            role="switch"
            aria-checked={hildeEnabled}
            aria-label="Hilde-Maskottchen anzeigen"
            className="flex items-start justify-between gap-4 px-3 py-3 rounded-lg cursor-pointer hover:bg-[var(--surface-dim)] transition-colors text-left w-full"
            style={{ border: "1px solid var(--border)" }}
          >
            <div className="flex flex-col gap-1 flex-1 min-w-0">
              <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                Hilde-Maskottchen
              </span>
              <span className="text-xs leading-snug" style={{ color: "var(--muted)" }}>
                Zeigt die Eulen-Begleiterin im Chat und auf Empty-States.
              </span>
            </div>
            <span
              className="relative shrink-0 mt-0.5 h-5 w-9 rounded-full transition-colors"
              style={{ backgroundColor: hildeEnabled ? "var(--kb)" : "var(--border)" }}
            >
              <span
                className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all"
                style={{ left: hildeEnabled ? "calc(100% - 1.125rem)" : "0.125rem" }}
              />
            </span>
          </button>
        </div>
      </Modal>
    </>
  );
}
