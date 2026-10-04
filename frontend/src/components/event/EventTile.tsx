"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { ROUTES } from "@/lib/event/routes";
import { EVENT_ICONS } from "@/lib/event/icons";
import { useText2 } from "@/lib/event/useText2";
import type { EventTile as EventTileData } from "@/lib/event/types";

export function tileHref(target: EventTileData["target"], signedIn = false): string {
  switch (target.kind) {
    case "stamp":
      return ROUTES.stamp;
    case "info":
      return ROUTES.info;
    case "internal":
      return target.path || "/";
    case "directLogin":
      // Whoever is signed in already must not get a second account from the code.
      return signedIn ? ROUTES.services : ROUTES.redeem(target.accessCode);
  }
}

function lockedNote(availableFrom: string, locale: string, t: (k: string, v?: Record<string, string>) => string): string {
  const day = availableFrom ? new Date(`${availableFrom}T12:00:00`) : null;
  if (!day || Number.isNaN(day.getTime())) return t("lockedSoon");
  const date = day.toLocaleDateString(locale === "en" ? "en-GB" : "de-DE", { day: "numeric", month: "long", year: "numeric" });
  return t("lockedFrom", { date });
}

export default function EventTile({ tile, signedIn = false }: { tile: EventTileData; signedIn?: boolean }) {
  const text = useText2();
  const t = useTranslations("eventBlock");
  const locale = useLocale();
  const Icon = EVENT_ICONS[tile.icon];
  const { variant } = useMascotPref();
  return (
    <div
      className="flex flex-col items-center text-center gap-3 border-2 border-[var(--tile-border)] rounded-2xl bg-[var(--tile-bg)] p-5 text-foreground"
      style={{ boxShadow: "var(--shadow)" }}
      data-testid="event-tile"
    >
      <div className="flex flex-col items-center gap-3">
        <span className="flex items-center justify-center w-14 h-14 shrink-0 rounded-full bg-kb text-on-accent">
          {tile.icon === "francis" ? (
            <Mascot variant={variant} size={52} state="idle" />
          ) : (
            <Icon size={28} weight="bold" aria-hidden="true" />
          )}
        </span>
        <span className="text-base font-semibold tracking-[-0.01em]">{text(tile.title)}</span>
      </div>
      <p className="text-sm leading-[21px] text-foreground-soft flex-1">{text(tile.body)}</p>
      {tile.active ? (
        <>
          <Link
            href={tileHref(tile.target, signedIn)}
            className="self-center px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap"
          >
            {text(tile.button)}
          </Link>
          <p className="text-xs -mt-1 invisible" aria-hidden="true">
            &nbsp;
          </p>
        </>
      ) : (
        <>
          <button
            type="button"
            disabled
            className="self-center px-3 py-2 text-sm btn-primary rounded-md whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="event-tile-locked"
          >
            {text(tile.button)}
          </button>
          <p className="text-xs text-foreground-soft -mt-1">{lockedNote(tile.availableFrom, locale, t)}</p>
        </>
      )}
    </div>
  );
}
