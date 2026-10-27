"use client";

import { useEffect, useState } from "react";
import { Link } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import { useText2 } from "@/lib/event/useText2";
import { inBanner, type EventBlock } from "@/lib/event/types";
import { tileHref } from "./EventTile";

/** Strip under the header built from the tile placed as banner, shown while the block runs and the tile is active. */
export default function EventBanner({ block }: { block: EventBlock | null }) {
  const text = useText2();
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    checkAuthStatus().then((s) => setSignedIn(s.authenticated));
  }, []);
  const tile = block?.tiles.find((t) => inBanner(t) && t.active);
  if (!block || !tile) return null;

  return (
    <div className="bg-kb text-on-accent border-t border-white/25" data-testid="event-banner">
      <div className="page-shell py-3 flex items-center justify-between gap-3 sm:justify-center sm:gap-5">
        <p className="text-sm leading-snug min-w-0">
          <strong className="block sm:inline sm:mr-2 text-base">{text(block.heading)}</strong>
          {text(tile.body)}
        </p>
        <Link
          href={tileHref(tile.target, signedIn)}
          className="shrink-0 rounded-lg border-2 border-white bg-white px-3 py-2 text-sm font-semibold text-kb hover:border-kb-dark transition-colors no-underline whitespace-nowrap"
        >
          {text(tile.button)}
        </Link>
      </div>
    </div>
  );
}
