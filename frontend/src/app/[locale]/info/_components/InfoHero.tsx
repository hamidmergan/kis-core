"use client";

import { useTranslations } from "next-intl";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import Band from "./Band";
import Screenshot from "./Screenshot";
import { useBandTop } from "./useBandTop";

const H1 = "font-semibold tracking-[-0.02em] leading-[1.05] text-kb! dark:text-kb-dark!";

/** Says what the pilot is in a headline and one sentence. */
export default function InfoHero({ layout = "split" }: { layout?: "split" | "center" }) {
  const t = useTranslations("eventInfo");
  const { variant } = useMascotPref();
  useBandTop("info-hero");
  if (layout === "center") {
    return (
      <Band tone="hero" testId="info-hero" fill>
        <div className="flex flex-col items-center text-center gap-6">
          <Mascot variant={variant} size={110} state="wave" />
          <h1 className={`${H1} text-4xl @min-[40rem]:text-6xl @min-[64rem]:text-7xl max-w-5xl text-balance`}>{t("title")}</h1>
          <p className="text-lg @min-[40rem]:text-xl @min-[80rem]:text-2xl leading-relaxed text-foreground-soft max-w-3xl">{t("lead")}</p>
          <Screenshot name="workspace" alt={t("heroAlt")} className="w-full max-w-6xl mt-8" />
        </div>
      </Band>
    );
  }
  return (
    <Band tone="hero" testId="info-hero" fill>
      <div className="grid grid-cols-1 @min-[48rem]:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] @min-[80rem]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-10 @min-[64rem]:gap-20 @min-[80rem]:gap-12 items-center">
        <div className="flex flex-col gap-6">
          <h1 className={`${H1} text-4xl @min-[56rem]:text-5xl @min-[64rem]:text-6xl @min-[80rem]:text-7xl @min-[96rem]:text-8xl`}>{t("title")}</h1>
          <p className="text-lg @min-[40rem]:text-xl @min-[80rem]:text-2xl leading-relaxed text-foreground-soft max-w-2xl text-balance">{t("lead")}</p>
        </div>
        <Screenshot name="workspace" alt={t("heroAlt")} />
      </div>
    </Band>
  );
}
