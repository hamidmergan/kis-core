"use client";

/**
 * Seitenleiste mit aufklappbarem Baum.
 *
 * Sieben Bereiche, mehr sieht man beim Öffnen nicht. Ein Klick klappt einen
 * Bereich auf und zeigt seine Unterseiten eingerückt, der vorher offene klappt
 * zu. So stehen nie mehr als sieben Zeilen plus die Unterseiten eines Bereichs
 * gleichzeitig da, statt wie vorher dreizehn Einträge in fünf Gruppen.
 *
 * Der offene Bereich ergibt sich aus der Adresse, nicht aus Klickzustand.
 * Damit ist ein Direktaufruf oder ein Lesezeichen sofort richtig aufgeklappt.
 */

import { CaretRight, X } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { RANKS, allowedSections, type AdminSection } from "./registry";
import { useAdminPerms, useIsFullAdmin } from "./AdminAuth";

const ICON = { size: 18, weight: "bold" as const };

/** Wohin der Bereichsname selbst fuehrt: auf die erste Unterseite, sonst auf
 *  den Bereich.
 *
 *  Die Liste ist hier schon nach Rechten gefiltert, versteckte Seiten muessen
 *  aber weiter uebersprungen werden. Sonst landete ein Klick auf "Nutzer" bei
 *  den Kontingenten, die ohne vorher gewaehlten Nutzer leer sind. */
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
  const t = useTranslations("admin");
  const perms = useAdminPerms();
  const fullAdmin = useIsFullAdmin();

  // Erst filtern, dann nach Rang buendeln. Wer nur eine Seite pflegen darf,
  // sieht genau diese eine Zeile, und leere Raenge fallen samt ihrer
  // Trennlinie weg.
  const visible = allowedSections(perms.keys);
  const blocks = RANKS
    .map((rank) => visible.filter((s) => s.rank === rank))
    .filter((group) => group.length > 0);

  return (
    <aside
      className={`bg-surface border-r border-border-soft p-3 flex flex-col gap-0.5 overflow-y-auto
        fixed md:sticky top-16 md:top-0 left-0 bottom-0 md:bottom-auto
        h-[calc(100vh-4rem)] md:h-screen
        w-72 md:w-68 z-40
        shadow-xl md:shadow-none
        transition-transform duration-200
        ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
    >
      <div className="md:hidden flex items-center justify-between px-2 pt-1 pb-2">
        <span className="text-sm font-semibold">{fullAdmin ? t("title") : t("titleSettings")}</span>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-muted transition-colors hover:bg-surface-dim hover:text-kb"
          aria-label={t("close")}
        >
          <X size={16} weight="bold" />
        </button>
      </div>

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
