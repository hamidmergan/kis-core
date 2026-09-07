"use client";

/** Tabs only where one thing splits into two views, the active one sits in the URL. */

import { Link } from "@/i18n/navigation";
import LinkBusy from "@/components/ui/LinkBusy";

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
            className={`inline-flex items-center gap-2 px-3 pt-2 pb-2.5 -mb-px text-sm border-b-2 transition-colors ${
              on
                ? "border-kb text-kb dark:text-white font-semibold"
                : "border-transparent text-muted hover:text-foreground-soft"
            }`}
          >
            {tab.label}
            <LinkBusy size="xs" />
          </Link>
        );
      })}
    </div>
  );
}
