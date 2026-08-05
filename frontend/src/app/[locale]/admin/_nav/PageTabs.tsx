"use client";

/**
 * Reiter innerhalb einer Seite.
 *
 * Bewusst sparsam. Unterseiten gehören in die Seitenleiste, weil sie zur
 * Navigation zählen. Reiter sind nur dann richtig, wenn ein Gegenstand in zwei
 * Ansichten auf dieselbe Sache zerfällt. Im Adminbereich trifft das zweimal zu,
 * beim Sprachniveau und bei den Anbietern.
 *
 * Der aktive Reiter steht in der Adresse (?ansicht=), damit ein Lesezeichen
 * auch die Ansicht trifft und die Zurück-Taste funktioniert.
 */

import { Link } from "@/i18n/navigation";

export default function PageTabs({
  base,
  tabs,
  active,
}: {
  base: string;
  tabs: { slug: string; label: string }[];
  active: string;
}) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1 border-b border-border-soft mb-6">
      {tabs.map((tab) => {
        const on = tab.slug === active;
        return (
          <Link
            key={tab.slug}
            role="tab"
            aria-selected={on}
            href={`${base}?ansicht=${tab.slug}`}
            className={`px-3 pt-2 pb-2.5 -mb-px text-sm border-b-2 transition-colors ${
              on
                ? "border-kb text-kb dark:text-white font-semibold"
                : "border-transparent text-muted hover:text-foreground-soft"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
