import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

/** Metadata of the legal pages: the site title, reachable but not indexed. */
export async function legalMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "layoutMeta" });
  return {
    title: t("title"),
    description: t("description"),
    // Legal pages stay reachable but out of search results, so name searches land on the start page.
    robots: { index: false, follow: true },
  };
}
