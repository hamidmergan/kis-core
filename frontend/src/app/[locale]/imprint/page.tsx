import type { Metadata } from "next";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

export async function generateMetadata({
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

export default function ImpressumPage() {
  const t = useTranslations("imprint");
  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
        <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8">
          <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>

          <p className="font-semibold text-foreground-soft mb-2">
            {t("lawHeading")}
          </p>
          <p className="text-foreground-soft mb-4">
            Hamid Mergan<br />
            Mönkhofer Weg 239<br />
            23562 Lübeck
          </p>

          <p className="font-semibold text-foreground-soft mb-2">{t("contactHeading")}</p>
          <p className="text-foreground-soft mb-4">
            {t("phoneLabel")} +49 451 160818 81<br />
            {t("emailLabel")} hamid.mergan@th-luebeck.de
          </p>

          <p className="font-semibold text-foreground-soft mb-2">{t("projectHeading")}</p>
          <p className="text-foreground-soft whitespace-pre-line">
            {t("projectBody")}
          </p>
        </div>
    </div>
  );
}
