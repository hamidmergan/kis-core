"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ROUTES } from "@/lib/event/routes";
import { EVENT_ICONS } from "@/lib/event/icons";
import { useText2 } from "@/lib/event/useText2";
import type { Text2 } from "@/lib/event/types";

/** The event's stamp card as a button beside the greeting, a link while it is open and a dated announcement before that, the admin's text shows on hover. */
export function StampButton({ stamp, from = "", title, body }: { stamp: "open" | "upcoming"; from?: string; title?: Text2; body?: Text2 }) {
  const t = useTranslations("startOverview");
  const text = useText2();
  const locale = useLocale();
  const Icon = EVENT_ICONS.star;
  const label = title ? text(title) : t("stamp.title");
  const hint = body ? text(body) : t("stamp.body");
  const day = from ? new Date(`${from}T12:00:00`) : null;
  const note =
    day && !Number.isNaN(day.getTime())
      ? t("stamp.from", { date: day.toLocaleDateString(locale === "en" ? "en-GB" : "de-DE", { day: "numeric", month: "long", year: "numeric" }) })
      : t("stamp.soon");
  const shell = "shrink-0 inline-flex items-center gap-2.5 rounded-xl border-2 px-2.5 sm:px-3.5 py-2 text-base font-semibold whitespace-nowrap";
  if (stamp === "upcoming") {
    return (
      <span className={`${shell} bg-background border-border text-muted`} title={`${note}. ${hint}`} aria-label={`${label}, ${note}`} data-testid="start-tile-stamp">
        <Icon size={22} weight="regular" aria-hidden />
        <span className="hidden sm:inline">{label}</span>
      </span>
    );
  }
  return (
    <Link
      href={ROUTES.stamp}
      aria-label={label}
      title={hint}
      className={`${shell} bg-background border-kb-dark text-kb-dark hover:border-kb transition-colors no-underline`}
      data-testid="start-tile-stamp"
    >
      <Icon size={22} weight="regular" aria-hidden />
      <span className="hidden sm:inline">{label}</span>
    </Link>
  );
}
