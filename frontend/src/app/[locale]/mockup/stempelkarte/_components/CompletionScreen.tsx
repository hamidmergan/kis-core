"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Gift } from "@phosphor-icons/react";
import Mascot, { type MascotVariant } from "@/components/ui/Mascot";

const ZONE = "Europe/Berlin";

/** Full card with a running clock, the visitor shows it at the info stand. */
export default function CompletionScreen({ variant, completedAt }: { variant: MascotVariant; completedAt: number | null }) {
  const t = useTranslations("mockup.stamp.complete");
  const locale = useLocale();
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const clock = new Intl.DateTimeFormat(locale, { timeZone: ZONE, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const day = new Intl.DateTimeFormat(locale, { timeZone: ZONE, weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const since = new Intl.DateTimeFormat(locale, { timeZone: ZONE, dateStyle: "short", timeStyle: "short" });

  return (
    <section
      className="flex flex-col items-center gap-4 rounded-2xl border-2 border-kb/15 bg-kb/5 p-6 text-center"
      data-testid="completion"
    >
      <Mascot variant={variant} size={120} state="wave" />
      <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h2>
      <div className="w-full rounded-2xl border-2 border-border bg-background px-4 py-5">
        <p className="text-xs uppercase tracking-[0.14em] text-muted">{t("clock")}</p>
        <p className="mt-1 text-4xl font-semibold tabular-nums text-kb" data-testid="completion-clock">
          {now ? clock.format(now) : "00:00:00"}
        </p>
        <p className="mt-1 text-sm text-foreground-soft">{now ? day.format(now) : ""}</p>
        {completedAt !== null && (
          <p className="mt-3 text-sm text-foreground-soft tabular-nums">{t("since", { time: since.format(new Date(completedAt)) })}</p>
        )}
      </div>
      <p className="text-sm text-foreground-soft">{t("clockHint")}</p>
      <p className="flex items-center gap-2 text-base font-medium text-foreground">
        <Gift size={22} weight="bold" aria-hidden="true" className="text-kb" />
        {t("reward")}
      </p>
    </section>
  );
}
