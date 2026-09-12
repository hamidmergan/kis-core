"use client";

import { useState } from "react";
import { CaretRight } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";


// Typed text is shown as its opening words, so only real file names count as a list.
const DATEINAME = /\.[A-Za-z0-9]{1,5}$/;

function namenListe(value: string): string[] {
  const teile = value.split(", ").map((n) => n.trim()).filter(Boolean);
  return teile.length > 1 && teile.every((n) => DATEINAME.test(n)) ? teile : [];
}


/** Several sources arrive as one comma joined string, only then it folds open. */
export function JobSources({ value }: { value: string }) {
  const [offen, setOffen] = useState(false);
  const t = useTranslations("myJobs.sources");
  const namen = namenListe(value);

  if (namen.length === 0) {
    return <p className="text-xs text-muted-soft truncate mt-0.5">{value}</p>;
  }

  return (
    <div className="mt-0.5">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOffen((v) => !v); }}
        aria-expanded={offen}
        className="flex items-center gap-1 max-w-full text-xs text-muted-soft hover:text-muted transition-colors"
      >
        <CaretRight
          size={10}
          weight="bold"
          className={`shrink-0 transition-transform ${offen ? "rotate-90" : ""}`}
          aria-hidden="true"
        />
        <span className="truncate">{namen[0]}</span>
        <span className="shrink-0 text-border">{t("more", { n: namen.length - 1 })}</span>
      </button>
      {offen && (
        <ul className="mt-1 space-y-0.5 border-l border-border-soft pl-3 text-xs text-muted-soft">
          {namen.map((name, i) => (
            <li key={`${i}-${name}`} className="truncate">{name}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
