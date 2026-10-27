"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import { useText2 } from "@/lib/event/useText2";
import type { EventBlock } from "@/lib/event/types";
import { tileHref } from "./EventTile";

/** Strip under the header with the demo login, shown while the block runs and its demo tile is active. */
export default function DemoBand({ block }: { block: EventBlock | null }) {
  const t = useTranslations("eventBlock.demoBand");
  const text = useText2();
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    checkAuthStatus().then((s) => setSignedIn(s.authenticated));
  }, []);
  const demo = block?.tiles.find((tile) => tile.target.kind === "directLogin" && tile.active);
  if (!block || !demo) return null;

  return (
    <div className="bg-kb text-on-accent border-t border-white/25" data-testid="demo-band">
      <div className="page-shell py-3 flex items-center justify-between gap-3 sm:justify-center sm:gap-5">
        <p className="text-sm leading-snug min-w-0">
          <strong className="block sm:inline sm:mr-2 text-base">{text(block.heading)}</strong>
          {t("text")}
        </p>
        <Link
          href={tileHref(demo.target, signedIn)}
          className="shrink-0 rounded-lg border-2 border-white bg-white px-3 py-2 text-sm font-semibold text-kb hover:border-kb-dark transition-colors no-underline whitespace-nowrap"
        >
          {t("button")}
        </Link>
      </div>
    </div>
  );
}
