"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { ROUTES } from "../../_lib/routes";
import Band from "./Band";
import ScreenshotSlot from "./ScreenshotSlot";

const H1 = "font-semibold tracking-[-0.02em] leading-[1.05] text-foreground!";

/** Says what the pilot is in three lines, the only button leads to the login. */
export default function InfoHero({ layout = "split" }: { layout?: "split" | "center" }) {
  const t = useTranslations("mockup.info");
  const tc = useTranslations("mockup.common");
  const { variant } = useMascotPref();
  const login = (
    <Link href={ROUTES.login} className="px-6 py-3 text-base font-medium rounded-md btn-primary" data-testid="info-login">
      {tc("login")}
    </Link>
  );
  const pill = (
    <p className="self-start rounded-full border border-kb/20 bg-kb/10 px-3.5 py-1.5 text-sm font-semibold text-kb-dark">
      {t("eyebrow")}
    </p>
  );
  if (layout === "center") {
    return (
      <Band tone="hero" testId="info-hero">
        <div className="flex flex-col items-center text-center gap-6">
          <Mascot variant={variant} size={110} state="wave" />
          <div className="self-center">{pill}</div>
          <h1 className={`${H1} text-4xl sm:text-6xl lg:text-7xl max-w-5xl text-balance`}>{t("title")}</h1>
          <p className="text-lg sm:text-xl xl:text-2xl leading-relaxed text-foreground-soft max-w-3xl">{t("lead")}</p>
          {login}
          <ScreenshotSlot className="w-full max-w-6xl mt-8" caption={t("heroCaption")} />
        </div>
      </Band>
    );
  }
  return (
    <Band tone="hero" testId="info-hero">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-10 lg:gap-20 items-center lg:py-8">
        <div className="flex flex-col gap-6">
          {pill}
          <h1 className={`${H1} text-4xl sm:text-5xl lg:text-6xl xl:text-7xl`}>{t("title")}</h1>
          <p className="text-lg sm:text-xl xl:text-2xl leading-relaxed text-foreground-soft max-w-2xl">{t("lead")}</p>
          <div className="flex">{login}</div>
        </div>
        <ScreenshotSlot caption={t("heroCaption")} />
      </div>
    </Band>
  );
}
