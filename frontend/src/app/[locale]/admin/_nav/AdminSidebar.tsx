"use client";

/** Sidebar with a collapsible tree, the open area follows the URL. */

import { CaretRight } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { RANKS, allowedSections, type AdminSection } from "./registry";
import { useAdminPerms } from "./AdminAuth";

const ICON = { size: 18, weight: "bold" as const };

/** The area name leads to the first visible subpage. */
function firstPath(s: AdminSection): string {
  if (!s.pages) return `/admin/${s.slug}`;
  const page = s.pages.find((p) => !p.hidden) ?? s.pages[0];
  return `/admin/${s.slug}/${page.slug}`;
}

function Group({
  section,
  openSlug,
  pageSlug,
  onNavigate,
}: {
  section: AdminSection;
  openSlug: string;
  pageSlug: string;
  onNavigate: () => void;
}) {
  const t = useTranslations("admin.sections");
  const open = section.slug === openSlug;
  const active = open && !section.pages;

  return (
    <div>
      <Link
        href={firstPath(section)}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        aria-expanded={section.pages ? open : undefined}
        className={`group w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-sm
          font-medium text-left transition-colors ${
            open
              ? "admin-nav-active text-kb dark:text-white font-semibold"
              : "text-foreground-soft hover:bg-surface-dim hover:text-kb dark:hover:text-white"
          }`}
      >
        <span
          className={`transition-colors ${
            open ? "text-kb dark:text-white" : "text-muted group-hover:text-kb dark:group-hover:text-white"
          }`}
        >
          <section.Icon {...ICON} />
        </span>
        <span className="flex-1 min-w-0">{t(`${section.key}.label`)}</span>
        {section.pages && (
          <CaretRight
            size={12}
            weight="bold"
            aria-hidden
            className={`shrink-0 opacity-60 transition-transform ${open ? "rotate-90" : ""}`}
          />
        )}
      </Link>

      {section.pages && open && (
        <div className="flex flex-col gap-px ml-[1.375rem] pl-[0.6875rem] mt-0.5 mb-1.5 border-l border-border-soft">
          {section.pages.filter((p) => !p.hidden).map((p) => {
            const on = p.slug === pageSlug;
            return (
              <Link
                key={p.slug}
                href={`/admin/${section.slug}/${p.slug}`}
                onClick={onNavigate}
                aria-current={on ? "page" : undefined}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  on
                    ? "admin-nav-active text-kb dark:text-white font-semibold"
                    : "text-foreground-soft hover:bg-surface-dim hover:text-kb dark:hover:text-white"
                }`}
              >
                {t(`${section.key}.${p.key}.label`)}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function AdminSidebar({
  openSlug,
  pageSlug,
  mobileOpen,
  onClose,
}: {
  openSlug: string;
  pageSlug: string;
  mobileOpen: boolean;
  onClose: () => void;
}) {
  const perms = useAdminPerms();

  // Filter first, then group, empty ranks drop out with their divider.
  const visible = allowedSections(perms.keys);
  const blocks = RANKS
    .map((rank) => visible.filter((s) => s.rank === rank))
    .filter((group) => group.length > 0);

  return (
    <aside
      id="admin-nav"
      // On the phone the tree sits inline under the dropdown, from md on it is the sticky column.
      className={`bg-surface border-border-soft p-3 flex-col gap-0.5
        w-full border-b
        md:sticky md:top-0 md:h-screen md:w-68 md:border-b-0 md:border-r md:overflow-y-auto
        ${mobileOpen ? "flex" : "hidden md:flex"}`}
    >
      {blocks.map((group, i) => (
        <div key={group[0].rank}>
          {i > 0 && <hr className="border-0 border-t border-border-soft mx-2 my-3" />}
          {group.map((s) => (
            <Group key={s.slug} section={s} openSlug={openSlug} pageSlug={pageSlug} onNavigate={onClose} />
          ))}
        </div>
      ))}
    </aside>
  );
}
