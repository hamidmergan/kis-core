"use client";

/**
 * Eine Route für alle Adminseiten. Welche Seite gemeint ist, entscheidet die
 * Registry, nicht diese Datei.
 *
 * Damit ist eine neue Seite ein Eintrag in der Registry und sonst nichts.
 * Vorher brauchte es drei Änderungen in page.tsx: Tab-Union, NAV-Array und
 * eine weitere Zeile in der Kette aus {tab === "x" && <XTab/>}.
 *
 * Unvollständige Adressen werden nach unten aufgefüllt: /admin landet beim
 * ersten Bereich, /admin/nutzer bei dessen erster Unterseite. Unbekannte
 * Adressen leiten auf den Anfang, statt eine leere Seite zu zeigen.
 */

import { use, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { allowed, firstAllowed, resolve } from "../_nav/registry";
import PageTabs from "../_nav/PageTabs";
import { useAdminPerms } from "../_nav/AdminAuth";

export default function AdminPage({ params }: { params: Promise<{ path?: string[] }> }) {
  const router = useRouter();
  const search = useSearchParams();
  const ts = useTranslations("admin.sections");

  const { path } = use(params);
  const segments = path ?? [];
  const perms = useAdminPerms();
  const found = resolve(segments);

  // Weiterleiten, wenn die Adresse unvollständig, unbekannt oder für diese
  // Person gesperrt ist. Eine gesperrte Adresse landet auf der ersten Seite,
  // die sie sehen darf, nicht auf einer leeren Seite und nicht auf der
  // markierten Startseite, die ihr genauso verwehrt sein kann.
  const mayOpen = found ? allowed(found, perms.keys) : false;
  const target = mayOpen ? found!.path : firstAllowed(perms.keys)?.path;
  const needsRedirect = !mayOpen || segments.join("/") !== target;
  useEffect(() => {
    if (needsRedirect) router.replace(`/admin/${target ?? ""}`);
  }, [needsRedirect, target, router]);

  if (!found || needsRedirect) return null;

  const { section, page } = found;
  const base = page ? `${section.key}.${page.key}` : section.key;

  // Reiter kann sowohl eine Unterseite haben als auch ein Bereich, der selbst
  // die Seite ist.
  const tabs = page?.tabs ?? section.tabs;
  const wanted = search.get("ansicht");
  const active = tabs ? (tabs.find((x) => x.slug === wanted) ?? tabs[0]) : null;
  const Body = active ? active.Component : (page?.Component ?? section.Component);
  if (!Body) return null;

  return (
    <>
      {page && (
        <p className="text-2xs font-semibold uppercase tracking-[0.09em] text-muted mb-1">
          {ts(`${section.key}.label`)}
        </p>
      )}
      <h2 className="text-lg font-semibold">{ts(`${base}.label`)}</h2>
      <p className="text-xs text-muted mt-1 mb-6 max-w-2xl">{ts(`${base}.sub`)}</p>

      {tabs && active && (
        <PageTabs
          base={page ? `/admin/${section.slug}/${page.slug}` : `/admin/${section.slug}`}
          tabs={tabs.map((x) => ({ slug: x.slug, label: ts(`${base}.tabs.${x.labelKey}`) }))}
          active={active.slug}
        />
      )}

      <Body />
    </>
  );
}
