"use client";

import { useLocale, useTranslations } from "next-intl";
import { ROUTES } from "@/lib/event/routes";
import { EVENT_ICONS } from "@/lib/event/icons";
import { useText2 } from "@/lib/event/useText2";
import type { Text2 } from "@/lib/event/types";
import { StartTile } from "./StartTile";

/** The event's stamp card, a link while it is open and an announcement with its date before that. */
export function StampTile({
  stamp,
  from = "",
  title,
  body,
}: {
  stamp: "open" | "upcoming";
  from?: string;
  title?: Text2;
  body?: Text2;
}) {
  const t = useTranslations("startOverview");
  const text = useText2();
  const locale = useLocale();
  const day = from ? new Date(`${from}T12:00:00`) : null;
  const note =
    day && !Number.isNaN(day.getTime())
      ? t("stamp.from", { date: day.toLocaleDateString(locale === "en" ? "en-GB" : "de-DE", { day: "numeric", month: "long", year: "numeric" }) })
      : t("stamp.soon");
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold uppercase tracking-wider">{t("groups.event")}</h2>
      <StartTile
        href={stamp === "open" ? ROUTES.stamp : undefined}
        note={stamp === "upcoming" ? note : undefined}
        icon={EVENT_ICONS.star}
        title={title ? text(title) : t("stamp.title")}
        body={body ? text(body) : t("stamp.body")}
        testId="start-tile-stamp"
      />
    </section>
  );
}
