"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ROUTES } from "../../_lib/routes";
import Band from "./Band";
import ScreenshotSlot from "./ScreenshotSlot";

/** Says what the pilot is in three lines, the only button leads to the login. */
export default function InfoHero() {
  const t = useTranslations("mockup.info");
  const tc = useTranslations("mockup.common");
  return (
    <Band tone="hero" testId="info-hero">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-10 lg:gap-20 lg:py-8 items-center">
        <div className="flex flex-col gap-6">
          <p className="self-start rounded-full border border-kb/20 bg-kb/10 px-3.5 py-1.5 text-sm font-semibold text-kb-dark">
            {t("eyebrow")}
          </p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-semibold tracking-[-0.02em] leading-[1.05] text-foreground!">
            {t("title")}
          </h1>
          <p className="text-lg sm:text-xl xl:text-2xl leading-relaxed text-foreground-soft max-w-2xl">{t("lead")}</p>
          <div className="flex">
            <Link href={ROUTES.login} className="px-6 py-3 text-base font-medium rounded-md btn-primary" data-testid="info-login">
              {tc("login")}
            </Link>
          </div>
        </div>
        <ScreenshotSlot caption={t("heroCaption")} />
      </div>
    </Band>
  );
}
