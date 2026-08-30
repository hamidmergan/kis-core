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
            <h2 className="text-lg font-semibold mb-2">
              {t("auth.heading")}
            </h2>
            <p className="text-foreground-soft mb-2">
              {t("auth.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>{t("auth.item1")}</li>
              <li>{t("auth.item2")}</li>
              <li>{t("auth.item3")}</li>
              <li>{t("auth.item4")}</li>
              <li>{t("auth.item5")}</li>
            </ul>
            <p className="text-foreground-soft mt-2 whitespace-pre-line">
              {t("auth.outro")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              {t("cookies.heading")}
            </h2>
            <p className="text-foreground-soft mb-2">
              {t("cookies.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>
                <strong>{t("cookies.sessionLabel")}</strong> - {t("cookies.sessionBody")}
              </li>
              <li>
                <strong>{t("cookies.storageLabel")}</strong> - {t("cookies.storageBody")}
              </li>
            </ul>
            <p className="text-foreground-soft mt-2">
              {t("cookies.outro")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              {t("jobs.heading")}
            </h2>
            <p className="text-foreground-soft mb-2">
              {t("jobs.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>{t("jobs.item1")}</li>
              <li>{t("jobs.item2")}</li>
              <li>{t("jobs.item3")}</li>
              <li>{t("jobs.item4")}</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              {t.rich("jobs.retention", {
                strong: (chunks) => <strong>{chunks}</strong>,
              })}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              {t("adminAccess.heading")}
            </h2>
            <p className="text-foreground-soft mb-2">
              {t("adminAccess.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>{t("adminAccess.item1")}</li>
              <li>{t("adminAccess.item2")}</li>
              <li>{t("adminAccess.item3")}</li>
              <li>{t("adminAccess.item4")}</li>
              <li>{t("adminAccess.item5")}</li>
              <li>{t("adminAccess.item6")}</li>
            </ul>
            <p className="text-foreground-soft mt-2 whitespace-pre-line">
              {t("adminAccess.outro")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              {t("thirdParty.heading")}
            </h2>
            <p className="text-foreground-soft mb-2">
              {t("thirdParty.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1 mb-2">
              <li>
                <strong>{t("thirdParty.kisskiLabel")}</strong> - {t("thirdParty.kisskiBody")}
              </li>
              <li>
                <strong>{t("thirdParty.mylabLabel")}</strong> - {t("thirdParty.mylabBody")}
              </li>
              <li>
                <strong>{t("thirdParty.deeplLabel")}</strong> - {t("thirdParty.deeplBody")}
              </li>
              <li>
                <strong>{t("thirdParty.hetznerLabel")}</strong> - {t("thirdParty.hetznerBody")}
              </li>
            </ul>
            <p className="text-foreground-soft">
              {t("thirdParty.outro")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">
              {t("logs.heading")}
            </h2>
            <p className="text-foreground-soft mb-2">
              {t("logs.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>{t("logs.item1")}</li>
              <li>{t("logs.item2")}</li>
              <li>{t("logs.item3")}</li>
              <li>{t("logs.item4")}</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              {t.rich("logs.retention", {
                strong: (chunks) => <strong>{chunks}</strong>,
              })}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("ssl.heading")}</h2>
            <p className="text-foreground-soft">
              {t("ssl.body")}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("legalBasis.heading")}</h2>
            <p className="text-foreground-soft">
              {t.rich("legalBasis.body", {
                strong: (chunks) => <strong>{chunks}</strong>,
              })}
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold mb-2">{t("rights.heading")}</h2>
            <p className="text-foreground-soft mb-2">
              {t("rights.intro")}
            </p>
            <ul className="list-disc pl-6 text-foreground-soft space-y-1">
              <li>{t("rights.item1")}</li>
              <li>{t("rights.item2")}</li>
              <li>{t("rights.item3")}</li>
              <li>{t("rights.item4")}</li>
              <li>{t("rights.item5")}</li>
              <li>{t("rights.item6")}</li>
            </ul>
            <p className="text-foreground-soft mt-2">
              {t("rights.contact")}{" "}
              <a href="mailto:hamid.mergan@th-luebeck.de" className="text-info hover:underline">
                hamid.mergan@th-luebeck.de
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-2">{t("complaint.heading")}</h2>
            <p className="text-foreground-soft">
              {t.rich("complaint.body", {
                strong: (chunks) => <strong>{chunks}</strong>,
              })}
            </p>
          </section>
        </div>
    </div>
  );
}
