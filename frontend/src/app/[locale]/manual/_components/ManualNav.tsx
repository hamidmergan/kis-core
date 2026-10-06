"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { CaretDown, MagnifyingGlass } from "@phosphor-icons/react";
import LinkBusy from "@/components/ui/LinkBusy";
import { checkAuthStatus } from "@/lib/auth";
import { filterTree } from "../_lib/filterTree";
import type { ManualGroup } from "../_lib/articles";

export default function ManualNav({ tree }: { tree: ManualGroup[] }) {
  const t = useTranslations("manual");
  // Die Nav steht im Layout und ueberlebt den Wechsel, den offenen Artikel liest sie deshalb aus der Adresse.
  const activeSlug = usePathname().split("/").pop() ?? "";
  const [query, setQuery] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  // Auf dem Handy steht sonst die ganze Liste vor dem Artikel.
  const [openOnPhone, setOpenOnPhone] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((s) => setIsAdmin(s.is_admin ?? false));
  }, []);

  const groups = filterTree(tree, query, isAdmin);
  const activeTitle = tree
    .flatMap((g) => g.articles)
    .find((a) => a.slug === activeSlug)?.title;

  return (
    <nav
      // Hoehe und Scrollen nur am breiten Schirm, sonst laeuft die Liste ueber den Artikel.
      className="w-full lg:w-60 shrink-0 lg:sticky lg:self-start lg:top-6 lg:overflow-y-auto lg:max-h-[calc(100vh-3rem)]"
      aria-label={t("navLabel")}
    >
      <button
        type="button"
        onClick={() => setOpenOnPhone((v) => !v)}
        aria-expanded={openOnPhone}
        className="lg:hidden w-full flex items-center gap-2 h-10 px-3 mb-4 rounded-lg text-sm font-medium"
        style={{
          backgroundColor: "var(--surface)",
          border: "1px solid var(--border)",
          color: "var(--foreground)",
        }}
      >
        <span className="flex-1 text-left truncate">{activeTitle ?? t("navLabel")}</span>
        <CaretDown
          size={14}
          weight="bold"
          aria-hidden="true"
          style={{ transform: openOnPhone ? "rotate(180deg)" : undefined }}
        />
      </button>

      <div className={`${openOnPhone ? "block" : "hidden"} lg:block`}>
      <div className="relative mb-4">
        <MagnifyingGlass
          size={15}
          weight="bold"
          aria-hidden
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-soft pointer-events-none"
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("filterPlaceholder")}
          aria-label={t("filterPlaceholder")}
          className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-border bg-background
                     text-foreground placeholder:text-muted-soft
                     focus:outline-none focus:border-kb focus:ring-3 focus:ring-kb/12"
        />
      </div>

      {groups.length === 0 && (
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          {t("noMatch")}
        </p>
      )}

      {groups.map((group, i) => (
        <div key={group.key} className={i === 0 ? "mb-5" : "mb-5 pt-5"}>
          <p
            // Trennlinie und Grossbuchstaben, sonst geht die Ueberschrift in den Titeln unter.
            className="text-2xs font-bold uppercase tracking-wider mb-2 pb-2 px-3"
            style={{
              color: "var(--kb)",
              borderBottom: "1px solid var(--border)",
            }}
          >
            {group.title}
          </p>
          <ul className="space-y-0.5">
            {group.articles.map((article) => {
              const active = article.slug === activeSlug;
              return (
                <li key={article.slug}>
                  <Link
                    href={`/manual/${article.slug}`}
                    onClick={() => setOpenOnPhone(false)}
                    aria-current={active ? "page" : undefined}
                    // btn-ghost bringt den Hover-Ring, der offene Eintrag zeigt denselben Ring dauerhaft.
                    // Der Ring liegt nach innen, sonst schneidet ihn die scrollende Nav links und rechts ab.
                    className="btn-ghost flex items-center gap-2 pl-5 pr-3 py-1.5 rounded-lg text-sm -outline-offset-2"
                    style={{
                      color: active ? "var(--kb-dark)" : "var(--foreground)",
                      outlineColor: active ? "var(--kb)" : undefined,
                      fontWeight: active ? 600 : 400,
                    }}
                  >
                    <span className="truncate">{article.title}</span>
                    <LinkBusy size="xs" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      </div>
    </nav>
  );
}
