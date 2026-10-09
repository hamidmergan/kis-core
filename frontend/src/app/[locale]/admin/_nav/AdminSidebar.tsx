"use client";

/** Sidebar with a collapsible tree, the open area follows the URL. */

import { useEffect, useState } from "react";
import { CaretRight } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import LinkBusy from "@/components/ui/LinkBusy";
import NoticeDot from "@/components/ui/NoticeDot";
import { useOpenFeedback } from "@/hooks/useOpenFeedback";
import { hasPerm, PERM } from "@/lib/permissions";
import { RANKS, allowedSections, type AdminPage, type AdminSection } from "./registry";
import { useAdminPerms } from "./AdminAuth";

const ICON = { size: 18, weight: "bold" as const };
const PHONE = "(max-width: 767px)";

/** The area name leads to the first visible subpage. */
function firstPath(s: AdminSection): string {
  if (!s.pages) return `/admin/${s.slug}`;
  const page = s.pages.find((p) => !p.hidden) ?? s.pages[0];
  return `/admin/${s.slug}/${page.slug}`;
}

function Group({
  section,
  open,
  current,
  pageSlug,
  notices,
  onToggle,
  onNavigate,
}: {
  section: AdminSection;
  open: boolean;
  current: boolean;
  pageSlug: string;
  notices: Record<NonNullable<AdminPage["notice"]>, boolean>;
  onToggle: () => void;
  onNavigate: () => void;
}) {
  const t = useTranslations("admin.sections");
  const tNotice = useTranslations("header");
  const active = current && !section.pages;
  const waits = (p: AdminPage) => !!p.notice && notices[p.notice];
  const sectionWaits = section.pages?.some((p) => !p.hidden && waits(p)) ?? false;

  // On the phone an area with subpages only unfolds, the jump belongs to the chosen subpage.
  function handleClick(e: React.MouseEvent) {
    if (section.pages && window.matchMedia(PHONE).matches) {
      e.preventDefault();
      onToggle();
      return;
    }
    onNavigate();
  }

  return (
    <div>
      <Link
        href={firstPath(section)}
        onClick={handleClick}
        aria-current={active ? "page" : undefined}
        aria-expanded={section.pages ? open : undefined}
        // btn-ghost brings the hover ring, the open page shows the same ring permanently.
        // An area with subpages stays without a ring, that one belongs to the open subpage.
        // The ring sits inwards, otherwise the scrolling sidebar clips it left and right.
        className={`btn-ghost w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-sm
          font-medium text-left -outline-offset-2 ${
            current ? "text-kb dark:text-white font-semibold" : "text-foreground-soft"
          }`}
        style={active ? { outlineColor: "var(--kb)" } : undefined}
      >
        <span className={current ? "text-kb dark:text-white" : "text-muted"}>
          <LinkBusy size="sm">
            <section.Icon {...ICON} />
          </LinkBusy>
        </span>
        <span className="flex-1 min-w-0">{t(`${section.key}.label`)}</span>
        {sectionWaits && <NoticeDot label={tNotice("openFeedback")} />}
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
            const on = current && p.slug === pageSlug;
            return (
              <Link
                key={p.slug}
                href={`/admin/${section.slug}/${p.slug}`}
                onClick={onNavigate}
                aria-current={on ? "page" : undefined}
                className={`btn-ghost flex items-center gap-2 px-3 py-1.5 rounded-md text-sm -outline-offset-2 ${
                  on ? "text-kb dark:text-white font-semibold" : "text-foreground-soft"
                }`}
                style={on ? { outlineColor: "var(--kb)" } : undefined}
              >
                <span className="truncate">{t(`${section.key}.${p.key}.label`)}</span>
                {waits(p) && <NoticeDot label={tNotice("openFeedback")} />}
                <LinkBusy size="xs" />
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
  const notices = { openFeedback: useOpenFeedback(hasPerm(perms, PERM.usersFeedback)) > 0 };
  const [expandedSlug, setExpandedSlug] = useState(openSlug);

  // The unfolded area follows the URL, opening the phone dropdown shows the current one again.
  useEffect(() => {
    setExpandedSlug(openSlug);
  }, [openSlug, mobileOpen]);

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
            <Group
              key={s.slug}
              section={s}
              open={s.slug === expandedSlug}
              current={s.slug === openSlug}
              pageSlug={pageSlug}
              notices={notices}
              onToggle={() => setExpandedSlug((v) => (v === s.slug ? "" : s.slug))}
              onNavigate={onClose}
            />
          ))}
        </div>
      ))}
    </aside>
  );
}
