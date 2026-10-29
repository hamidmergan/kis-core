"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { CaretDown, MagnifyingGlass, X } from "@phosphor-icons/react";
import LinkBusy from "@/components/ui/LinkBusy";
import { checkAuthStatus } from "@/lib/auth";
import { filterTree } from "../_lib/filterTree";
import type { ManualGroup } from "../_lib/articles";

export default function ManualNav({ tree }: { tree: ManualGroup[] }) {
  const t = useTranslations("manual");
  // The nav lives in the layout and survives navigation, so it reads the open article from the URL.
  const activeSlug = usePathname().split("/").pop() ?? "";
  const [query, setQuery] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const filterInput = useRef<HTMLInputElement>(null);
  // On the phone the whole list would otherwise sit before the article.
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
      // Height and scrolling only on wide screens, otherwise the list overflows the article.
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
          ref={filterInput}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("filterPlaceholder")}
          aria-label={t("filterPlaceholder")}
          className="w-full pl-9 pr-9 py-2 text-sm rounded-lg border-2 border-border bg-background
                     text-foreground placeholder:text-muted-soft transition-colors
                     hover:border-kb focus:outline-none focus:border-kb"
        />
        {query && (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              filterInput.current?.focus();
            }}
            aria-label={t("filterClear")}
            title={t("filterClear")}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-full btn-icon"
          >
            <X size={14} weight="bold" />
          </button>
        )}
      </div>

      {groups.length === 0 && (
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          {t("noMatch")}
        </p>
      )}

      {groups.map((group, i) => (
        <div key={group.key} className={i === 0 ? "mb-5" : "mb-5 pt-5"}>
          <p
            // Rule and capitals, otherwise the heading drowns among the titles.
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
                    // btn-ghost gives the other entries the hover ring; the open entry gets a fill and keeps its ring transparent so hover adds none. The ring is inset, otherwise the scrolling nav clips it.
                    className={`btn-ghost flex items-center gap-2 pl-5 pr-3 py-1.5 rounded-lg text-sm -outline-offset-2 ${active ? "bg-kb/10" : ""}`}
                    style={{
                      color: active ? "var(--kb-dark)" : "var(--foreground)",
                      outlineColor: active ? "transparent" : undefined,
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
