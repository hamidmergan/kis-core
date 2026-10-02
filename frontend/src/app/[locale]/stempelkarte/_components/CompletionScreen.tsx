"use client";

import { useLocale, useTranslations } from "next-intl";
import { Gift } from "@phosphor-icons/react";
import Mascot, { type MascotVariant } from "@/components/ui/Mascot";

const ZONE = "Europe/Berlin";

/** Full card, the visitor shows it at the info stand. */
export default function CompletionScreen({ variant, completedAt }: { variant: MascotVariant; completedAt: number | null }) {
  const t = useTranslations("eventStamp.complete");
  const locale = useLocale();
  const since = new Intl.DateTimeFormat(locale, { timeZone: ZONE, hour: "2-digit", minute: "2-digit" });

  return (
    <section
      className="flex flex-col items-center gap-4 rounded-2xl border-2 border-kb/15 bg-kb/5 p-6 text-center"
      data-testid="completion"
    >
      <Mascot variant={variant} size={120} state="wave" />
      <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h2>
      {completedAt !== null && (
        <p className="text-sm text-foreground-soft tabular-nums">{t("since", { time: since.format(new Date(completedAt)) })}</p>
      )}
      <p className="flex items-center gap-2 text-base font-medium text-foreground">
        <Gift size={22} weight="bold" aria-hidden="true" className="text-kb" />
        {t("reward")}
      </p>
    </section>
  );
}
