"use client";

import { Link } from "@/i18n/navigation";
import { ROUTES } from "../_lib/routes";
import { MOCKUP_ICONS } from "../_lib/icons";
import { useText2 } from "../_lib/useText2";
import type { EventTile as EventTileData } from "../_lib/types";

export function tileHref(target: EventTileData["target"]): string {
  switch (target.kind) {
    case "stamp":
      return ROUTES.stamp;
    case "info":
      return ROUTES.info;
    case "internal":
      return target.path || ROUTES.overview;
    case "directLogin":
      return ROUTES.redeem(target.accessCode);
  }
}

export default function EventTile({ tile }: { tile: EventTileData }) {
  const text = useText2();
  const Icon = MOCKUP_ICONS[tile.icon];
  return (
    <div
      className="flex flex-col gap-3 border-2 border-[var(--tile-border)] rounded-2xl bg-[var(--tile-bg)] p-5 text-foreground"
      style={{ boxShadow: "var(--shadow)" }}
      data-testid="event-tile"
    >
      <div className="flex items-center gap-4">
        <span className="flex items-center justify-center w-14 h-14 shrink-0 rounded-full bg-kb text-on-accent">
          <Icon size={28} weight="bold" aria-hidden="true" />
        </span>
        <span className="text-base font-semibold tracking-[-0.01em]">{text(tile.title)}</span>
      </div>
      <p className="text-sm leading-[21px] text-foreground-soft flex-1">{text(tile.body)}</p>
      <Link
        href={tileHref(tile.target)}
        className="self-start px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap"
      >
        {text(tile.button)}
      </Link>
    </div>
  );
}
