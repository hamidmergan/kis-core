"use client";

/** Frame of the admin area: access check, sidebar, dropdown for the phone. */

import { useState } from "react";
import { CaretDown } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { usePathname } from "@/i18n/navigation";
import AdminAuth from "./_nav/AdminAuth";
import AdminSidebar from "./_nav/AdminSidebar";
import { SettingsProvider } from "./_settings/SettingsProvider";
import { resolve } from "./_nav/registry";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const ts = useTranslations("admin.sections");
  const pathname = usePathname();
  const [navOpen, setNavOpen] = useState(false);

  // Derived from the URL so a direct call expands correctly.
  const segments = pathname.replace(/^\/admin\/?/, "").split("/").filter(Boolean);
  const found = resolve(segments);
  const openSlug = found?.section.slug ?? "";
  const pageSlug = found?.page?.slug ?? "";
  // On the phone this line replaces the page eyebrow, so it carries the area too.
  const crumb = found
    ? found.page
      ? `${ts(`${found.section.key}.label`)} › ${ts(`${found.section.key}.${found.page.key}.label`)}`
      : ts(`${found.section.key}.label`)
    : "";

  return (
    <AdminAuth>
      <SettingsProvider>
        <div className="flex flex-col md:flex-row min-h-[calc(100vh-4rem)]">
          <div className="md:hidden px-4 py-2 border-b border-border-soft bg-background sticky top-0 z-20">
            <button
              type="button"
              onClick={() => setNavOpen((v) => !v)}
              aria-expanded={navOpen}
              aria-controls="admin-nav"
              className="w-full flex items-center gap-2 h-10 px-3 rounded-lg bg-surface border border-border text-sm font-medium text-foreground transition-colors hover:border-kb"
            >
              <span className="flex-1 text-left truncate">{crumb}</span>
              <CaretDown
                size={14}
                weight="bold"
                aria-hidden
                className={`shrink-0 opacity-60 transition-transform ${navOpen ? "rotate-180" : ""}`}
              />
            </button>
          </div>

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
