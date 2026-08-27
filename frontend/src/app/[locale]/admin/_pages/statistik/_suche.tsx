"use client";

/** Search field with a result list, shared by people and modules. */

import { useEffect, useRef, useState } from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";

export interface Treffer {
  id: string;
  titel: string;
  zusatz?: string;
}

export function Suche({
  eintraege,
  platzhalter,
  gewaehlt,
  waehlen,
  nichtsGefunden,
}: {
  eintraege: Treffer[];
  platzhalter: string;
  gewaehlt: string | null;
  waehlen: (id: string) => void;
  nichtsGefunden: string;
}) {
  const [text, setText] = useState("");
  const [offen, setOffen] = useState(false);
  const rahmen = useRef<HTMLDivElement>(null);

  // A click outside closes the list, otherwise it covers the content.
  useEffect(() => {
    const zu = (e: MouseEvent) => {
      if (!rahmen.current?.contains(e.target as Node)) setOffen(false);
    };
    document.addEventListener("mousedown", zu);
    return () => document.removeEventListener("mousedown", zu);
  }, []);

  const suchtext = text.trim().toLowerCase();
  const treffer = suchtext
    ? eintraege.filter((e) =>
        `${e.titel} ${e.zusatz ?? ""}`.toLowerCase().includes(suchtext),
      )
    : eintraege;

  return (
    <div ref={rahmen} className="relative mt-4 max-w-md">
      <MagnifyingGlass
        size={16}
        weight="bold"
        aria-hidden
        className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-soft pointer-events-none"
      />
      <input
        type="search"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOffen(true);
        }}
        onFocus={() => setOffen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOffen(false);
        }}
        placeholder={platzhalter}
        aria-label={platzhalter}
        className="w-full pl-9 pr-3 py-2.5 text-sm rounded-lg border border-border bg-background
                   text-foreground placeholder:text-muted-soft
                   focus:outline-none focus:border-kb focus:ring-3 focus:ring-kb/12"
      />

      {offen && (
        <div
          className="absolute z-20 left-0 right-0 top-full mt-1.5 max-h-64 overflow-y-auto
                     rounded-lg border border-border-soft bg-background shadow-lg"
        >
          {treffer.length === 0 ? (
            <p className="px-3.5 py-3 text-sm text-muted-soft">{nichtsGefunden}</p>
          ) : (
            treffer.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => {
                  waehlen(e.id);
                  setText(e.titel);
                  setOffen(false);
                }}
                aria-current={gewaehlt === e.id ? "true" : undefined}
                className={`flex w-full items-baseline gap-2 px-3.5 py-2 text-left text-sm
                            transition-colors hover:bg-surface ${
                              gewaehlt === e.id ? "bg-surface font-medium" : "text-foreground-soft"
                            }`}
              >
                <span className="truncate">{e.titel}</span>
                {e.zusatz && (
                  <span className="ml-auto shrink-0 text-xs text-muted-soft">{e.zusatz}</span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

/** Placeholder while nothing is selected. */
export function NochNichts({ text }: { text: string }) {
  return (
    <div className="mt-4 rounded-xl border border-dashed border-border px-4 py-9 text-center text-sm text-muted-soft">
      {text}
    </div>
  );
}
