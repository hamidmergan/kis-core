"use client";

import { CaretDown } from "@phosphor-icons/react";
import type { ReactNode } from "react";

/** One setting: a collapsible row with its value on the phone, a plain labelled field on the desktop. */
export default function EinstellungsFeld({ titel, wert, offen, onToggle, htmlFor, desktopTitel = true, className = "order-3 lg:mt-6", children }: {
  titel: string;
  wert: string;
  offen: boolean;
  onToggle: () => void;
  htmlFor?: string;
  desktopTitel?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`border-b border-border-soft lg:border-0 ${className}`}>
      <button type="button" onClick={onToggle} aria-expanded={offen}
              className="lg:hidden w-full px-4 py-3.5 flex items-center justify-between gap-3 text-left">
        <span className="text-sm font-medium shrink-0">{titel}</span>
        <span className="flex items-center gap-2 min-w-0">
          <span className="text-sm text-muted truncate">{wert}</span>
          <CaretDown size={14} weight="bold" className={`text-muted shrink-0 transition-transform ${offen ? "rotate-180" : ""}`} />
        </span>
      </button>
      {desktopTitel && (htmlFor
        ? <label htmlFor={htmlFor} className="hidden lg:block text-sm font-medium mb-1">{titel}</label>
        : <p className="hidden lg:block text-sm font-medium mb-2">{titel}</p>)}
      <div className={`${offen ? "block" : "hidden"} lg:block px-4 pb-4 lg:p-0`}>{children}</div>
    </div>
  );
}
