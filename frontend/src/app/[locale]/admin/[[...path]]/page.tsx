"use client";

/** One route for all admin pages, the registry decides which. */

import { use, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { allowed, allowedTabs, firstAllowed, resolve } from "../_nav/registry";
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

  // Incomplete or blocked URLs land on a permitted page.
  const mayOpen = found ? allowed(found, perms.keys) : false;
  const target = mayOpen ? found!.path : firstAllowed(perms.keys)?.path;
  const needsRedirect = !mayOpen || segments.join("/") !== target;
  useEffect(() => {
    if (needsRedirect) router.replace(`/admin/${target ?? ""}`);
  }, [needsRedirect, target, router]);

  if (!found || needsRedirect) return null;

  const { section, page } = found;
  const base = page ? `${section.key}.${page.key}` : section.key;

  // The tabs are filtered too, each hangs off its own permission.
  const tabs = page
    ? allowedTabs(page.tabs, page.perm, perms.keys)
    : allowedTabs(section.tabs, section.perm, perms.keys);
  const wanted = search.get("ansicht");
  const active = tabs.length ? (tabs.find((x) => x.slug === wanted) ?? tabs[0]) : null;
  const Body = active ? active.Component : (page?.Component ?? section.Component);
  if (!Body) return null;

  // Not every page needs a subtitle line.
  const hasSub = ts.has(`${base}.sub`);

  return (
    <>
      {page && (
        <p className="hidden md:block text-2xs font-semibold uppercase tracking-[0.09em] text-muted mb-1">
          {ts(`${section.key}.label`)}
        </p>
      )}
      <h2 className={`text-lg font-semibold${hasSub ? "" : " mb-6"}`}>{ts(`${base}.label`)}</h2>
      {hasSub && <p className="text-xs text-muted mt-1 mb-6 max-w-2xl">{ts(`${base}.sub`)}</p>}

      {active && tabs.length > 1 && (
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
