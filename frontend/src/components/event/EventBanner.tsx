"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import { useText2 } from "@/lib/event/useText2";
import { inBanner, type EventBlock } from "@/lib/event/types";
import { lockedNote, tileHref } from "./EventTile";

/** Strip under the header built from the tile placed as banner, a locked tile shows its button greyed with the unlock date. */
export default function EventBanner({ block }: { block: EventBlock | null }) {
  const text = useText2();
  const t = useTranslations("eventBlock");
  const locale = useLocale();
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    checkAuthStatus().then((s) => setSignedIn(s.authenticated));
  }, []);
  const tile = block?.tiles.find(inBanner);
  if (!block || !tile) return null;

  return (
    <div className="bg-kb text-on-accent border-t border-white/25" data-testid="event-banner">
      <div className="page-shell py-3 flex items-center justify-between gap-3 sm:justify-center sm:gap-5">
        <p className="text-sm leading-snug min-w-0">
          <strong className="block sm:inline sm:mr-2 text-base">{text(block.heading)}</strong>
          {text(tile.body)}
        </p>
        {tile.active ? (
          <Link
            href={tileHref(tile.target, signedIn)}
            className="shrink-0 rounded-lg border-2 border-white bg-white px-3 py-2 text-sm font-semibold text-kb hover:border-kb-dark transition-colors no-underline whitespace-nowrap"
          >
            {text(tile.button)}
          </Link>
        ) : (
          <span className="shrink-0 flex flex-col items-center gap-0.5">
            <button
              type="button"
              disabled
              className="rounded-lg border-2 border-white bg-white px-3 py-2 text-sm font-semibold text-kb whitespace-nowrap opacity-50 cursor-not-allowed"
              data-testid="event-banner-locked"
            >
              {text(tile.button)}
            </button>
            <span className="text-xs text-on-accent/85 whitespace-nowrap">{lockedNote(tile.availableFrom, locale, t)}</span>
          </span>
        )}
      </div>
    </div>
  );
}
