"use client";

import { Star } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";

/** The styles of the image tool above a picture instruction, a choice fills the field and an own text marks none. */
export default function StilChips({ stile, standard, wert, onWahl, disabled }: {
  stile: Record<string, string>;
  standard: string;
  wert: string;
  onWahl: (text: string) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("tools.image.options");
  const gewaehlt = wert.trim();
  return (
    <div className="flex flex-wrap gap-2 mb-2" role="radiogroup" aria-label={t("style")}>
      {Object.entries(stile).map(([key, text]) => {
        const aktiv = gewaehlt === text.trim();
        return (
          <button key={key} type="button" role="radio" aria-checked={aktiv} disabled={disabled} onClick={() => onWahl(text)}
            className={`inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md border-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              aktiv ? "border-kb bg-kb/10 text-kb dark:text-foreground" : "border-border bg-background text-foreground-soft hover:border-kb"
            }`}>
            {key === standard && <Star size={12} weight="fill" className="text-kb-dark" aria-label={t("defaultStyle")} />}
            {t(`styles.${key}`)}
          </button>
        );
      })}
    </div>
  );
}
