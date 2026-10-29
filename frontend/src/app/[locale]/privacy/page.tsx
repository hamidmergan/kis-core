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

export default function DatenschutzPage() {
  const t = useTranslations("privacy");
  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
        <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8">
          <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("controller.heading")}</h2>
            <p className="text-foreground-soft whitespace-pre-line">
              {t("controller.body")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("data.heading")}</h2>
            <p className="text-foreground-soft mb-2">
              {t("data.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>{t("data.item1")}</li>
              <li>{t("data.item2")}</li>
              <li>{t("data.item3")}</li>
              <li>{t("data.item4")}</li>
              <li>{t("data.item5")}</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              {t("data.outro")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("cookies.heading")}</h2>
            <p className="text-foreground-soft">
              {t("cookies.body")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("recipients.heading")}</h2>
            <p className="text-foreground-soft whitespace-pre-line">
              {t("recipients.body")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("retention.heading")}</h2>
            <p className="text-foreground-soft">
              {t("retention.body")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("legalBasis.heading")}</h2>
            <p className="text-foreground-soft">
              {t("legalBasis.body")}
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">{t("rights.heading")}</h2>
            <p className="text-foreground-soft">
              {t("rights.body")}{" "}
              <a href="mailto:hamid.mergan@th-luebeck.de" className="text-info hover:underline">
                hamid.mergan@th-luebeck.de
              </a>
              .
            </p>
            <p className="text-foreground-soft mt-2">
              {t("rights.complaint")}
            </p>
          </section>
        </div>
    </div>
  );
}
