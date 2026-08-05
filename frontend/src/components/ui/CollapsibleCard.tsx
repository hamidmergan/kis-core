"use client";

import { useState, type ReactNode } from "react";
import { CaretRight } from "@phosphor-icons/react";

/**
 * Karte mit einklappbarem Inhalt. Kopfzeile aus Titel und Beschreibung bleibt
 * immer sichtbar, der Rest faehrt aus und ein.
 *
 * Der Inhalt wird versteckt statt ausgehaengt, damit geladene Einstellungen und
 * angefangene Eingaben beim Zuklappen erhalten bleiben.
 */
export default function CollapsibleCard({
  title,
  badge,
  description,
  defaultOpen = false,
  children,
}: {
  title: ReactNode;
  /** Platzhaltername in Schreibmaschinenschrift neben dem Titel, z.B. {grading}. */
  badge?: string;
  description?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-border-soft rounded-xl bg-background">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`w-full text-left flex items-start gap-2 px-5 pt-5 rounded-xl transition-colors hover:bg-surface ${
          open ? "pb-4" : "pb-5"
        }`}
      >
        <CaretRight
          size={12}
          weight="bold"
          className={`mt-1 flex-shrink-0 text-muted-soft transition-transform ${open ? "rotate-90" : ""}`}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-foreground">
            {title}
            {badge && (
              <span className="ml-2 text-xs font-mono font-normal text-muted-soft">{badge}</span>
            )}
          </span>
          {description && <span className="block text-xs text-muted mt-1">{description}</span>}
        </span>
      </button>
      <div className={open ? "px-5 pb-5" : "hidden"}>{children}</div>
    </div>
  );
}
