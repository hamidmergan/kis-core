"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { ROUTES } from "../../_lib/routes";
import Band from "./Band";
import Screenshot from "./Screenshot";
import { useBandTop } from "./useBandTop";

const H1 = "font-semibold tracking-[-0.02em] leading-[1.05] text-foreground!";

/** Says what the pilot is in three lines, the only button leads to the login. */
export default function InfoHero({ layout = "split" }: { layout?: "split" | "center" }) {
  const t = useTranslations("mockup.info");
  const tc = useTranslations("mockup.common");
  const { variant } = useMascotPref();
  useBandTop("info-hero");
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
      <Band tone="hero" testId="info-hero" fill>
        <div className="flex flex-col items-center text-center gap-6">
          <Mascot variant={variant} size={110} state="wave" />
          <div className="self-center">{pill}</div>
          <h1 className={`${H1} text-4xl @min-[40rem]:text-6xl @min-[64rem]:text-7xl max-w-5xl text-balance`}>{t("title")}</h1>
          <p className="text-lg @min-[40rem]:text-xl @min-[80rem]:text-2xl leading-relaxed text-foreground-soft max-w-3xl">{t("lead")}</p>
          {login}
          <Screenshot name="workspace" alt={t("heroAlt")} className="w-full max-w-6xl mt-8" />
        </div>
      </Band>
    );
  }
  return (
    <Band tone="hero" testId="info-hero" fill>
      <div className="grid grid-cols-1 @min-[48rem]:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-10 @min-[64rem]:gap-20 items-center">
        <div className="flex flex-col gap-6">
          {pill}
          <h1 className={`${H1} text-4xl @min-[56rem]:text-5xl @min-[64rem]:text-6xl @min-[80rem]:text-7xl @min-[96rem]:text-8xl`}>{t("title")}</h1>
          <p className="text-lg @min-[40rem]:text-xl @min-[80rem]:text-2xl leading-relaxed text-foreground-soft max-w-2xl">{t("lead")}</p>
          <div className="flex">{login}</div>
        </div>
        <Screenshot name="workspace" alt={t("heroAlt")} />
      </div>
    </Band>
  );
}
