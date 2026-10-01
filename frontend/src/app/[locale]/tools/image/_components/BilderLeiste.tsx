"use client";

import { useTranslations } from "next-intl";
import type { BildErgebnis } from "./useBildAuftraege";

/** All pictures as small tiles, a click shows one large, a second click on the same one clears the choice. */
export default function BilderLeiste({ bilder, gewaehlt, onWaehlen }: {
  bilder: BildErgebnis[];
  gewaehlt: string;
  onWaehlen: (key: string) => void;
}) {
  const t = useTranslations("tools.image.history");
  return (
    <div className="mt-10">
      <h2 className="text-sm font-semibold text-foreground mb-1">{t("title")}</h2>
      <p className="text-xs text-muted mb-3">{bilder.length ? t("hint") : t("empty")}</p>
      {/* On a phone one row to swipe, otherwise the tiles would push the form far down. */}
      <div className="flex gap-2 overflow-x-auto pb-1 sm:grid sm:grid-cols-6 lg:grid-cols-8 sm:overflow-visible sm:pb-0">
        {bilder.map((b) => (
          <button
            key={b.key}
            type="button"
            onClick={() => onWaehlen(b.key)}
            aria-label={t("open", { name: b.beschreibung ?? b.filename })}
            aria-pressed={b.key === gewaehlt}
            className={`w-20 shrink-0 sm:w-auto rounded-md border-2 p-0.5 transition-colors ${
              b.key === gewaehlt ? "border-kb" : "border-border-soft hover:border-kb"
            }`}
          >
            <img src={b.url} alt="" className="aspect-square w-full rounded object-cover" />
          </button>
        ))}
      </div>
    </div>
  );
}
