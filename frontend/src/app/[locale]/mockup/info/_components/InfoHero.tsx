"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ROUTES } from "../../_lib/routes";
import ScreenshotSlot from "./ScreenshotSlot";

/** Says what the pilot is in three lines, the only button leads to the login. */
export default function InfoHero() {
  const t = useTranslations("mockup.info");
  const tc = useTranslations("mockup.common");
  return (
    <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:items-center" data-testid="info-hero">
      <div className="flex flex-col gap-4">
        <p className="text-sm font-semibold uppercase tracking-wider text-kb-dark">{t("eyebrow")}</p>
        <h1 className="text-3xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h1>
        <p className="text-base text-foreground-soft max-w-prose">{t("lead")}</p>
        <div className="flex">
          <Link href={ROUTES.login} className="px-4 py-2 text-sm font-medium rounded-md btn-primary" data-testid="info-login">
            {tc("login")}
          </Link>
        </div>
      </div>
      <ScreenshotSlot caption={t("heroCaption")} />
    </section>
  );
}
