"use client";

/**
 * Rahmen des Adminbereichs: Zugangsprüfung, Seitenleiste, Schublade fürs Handy.
 *
 * Steht als Layout über allen Adminseiten, damit die Seitenleiste beim Wechsel
 * nicht neu aufgebaut wird und der Zugang nur einmal geprüft werden muss.
 */

import { useState } from "react";
import { List } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { usePathname } from "@/i18n/navigation";
import AdminAuth from "./_nav/AdminAuth";
import AdminSidebar from "./_nav/AdminSidebar";
import { SettingsProvider } from "./_settings/SettingsProvider";
import { resolve } from "./_nav/registry";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("admin");
  const ts = useTranslations("admin.sections");
  const pathname = usePathname();
  const [navOpen, setNavOpen] = useState(false);

  // Aus der Adresse ableiten statt mitzuzählen: ein Direktaufruf ist damit
  // sofort richtig aufgeklappt.
  const segments = pathname.replace(/^\/admin\/?/, "").split("/").filter(Boolean);
  const found = resolve(segments);
  const openSlug = found?.section.slug ?? "";
  const pageSlug = found?.page?.slug ?? "";
  const crumb = found
    ? found.page
      ? ts(`${found.section.key}.${found.page.key}.label`)
      : ts(`${found.section.key}.label`)
    : "";

  return (
    <AdminAuth>
      <SettingsProvider>
        <div className="flex flex-col md:flex-row min-h-[calc(100vh-4rem)]">
          <div className="md:hidden flex items-center gap-3 px-4 h-12 border-b border-border-soft bg-background sticky top-0 z-20">
            <button
              onClick={() => setNavOpen(true)}
              className="w-9 h-9 rounded-lg bg-surface border-2 border-transparent flex items-center justify-center text-muted transition-colors hover:border-kb hover:text-kb"
              aria-label={t("menuOpen")}
            >
              <List size={18} weight="bold" />
            </button>
            <div className="text-sm font-medium text-foreground-soft truncate">{crumb}</div>
          </div>

          {navOpen && (
            <button
              onClick={() => setNavOpen(false)}
              aria-label={t("menuClose")}
              className="md:hidden fixed inset-0 top-16 bg-black/40 z-30"
            />
          )}

          <AdminSidebar
            openSlug={openSlug}
            pageSlug={pageSlug}
            mobileOpen={navOpen}
            onClose={() => setNavOpen(false)}
          />

          <main className="flex-1 min-w-0 px-4 py-6 md:px-8 md:py-8 lg:px-10">
            <div className="max-w-5xl mx-auto">{children}</div>
          </main>
        </div>
      </SettingsProvider>
    </AdminAuth>
  );
}
