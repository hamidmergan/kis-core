"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { CaretDown, List } from "@phosphor-icons/react";
import { checkAuthStatus } from "@/lib/auth";
import { filterTree } from "../_lib/filterTree";
import type { ManualGroup } from "../_lib/articles";

export default function ManualNav({ tree, activeSlug }: { tree: ManualGroup[]; activeSlug: string }) {
  const t = useTranslations("manual");
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
        <List size={16} weight="bold" aria-hidden="true" />
        <span className="flex-1 text-left truncate">{activeTitle ?? t("navLabel")}</span>
        <CaretDown
          size={14}
          weight="bold"
          aria-hidden="true"
          style={{ transform: openOnPhone ? "rotate(180deg)" : undefined }}
        />
      </button>

      <div className={`${openOnPhone ? "block" : "hidden"} lg:block`}>
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
                    className="block pl-5 pr-3 py-1.5 rounded-lg text-sm transition-colors"
                    style={{
                      color: active ? "var(--kb-dark)" : "var(--foreground)",
                      backgroundColor: active ? "var(--surface-dim)" : "transparent",
                      fontWeight: active ? 600 : 400,
                    }}
                  >
                    {article.title}
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
