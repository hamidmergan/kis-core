"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Compass } from "@phosphor-icons/react";
import { useTourStart } from "./useTourStart";
import { ladeTourGesehen, merkeTourGesehen } from "../[uuid]/_tour/tourSeen";

/**
 * Entry into the guided tour, on the start page.
 *
 * Only appears while there is something to show: a demo course has to exist,
 * and whoever walked the tour to its last step or waved it off does not see it
 * again, while breaking off midway leaves it standing. Pressing start joins the
 * demo course in the background, so nobody has to find the demo dialog first.
 */
export function TourInvite() {
  const t = useTranslations("workspace.detail.tour");
  const tour = useTourStart();
  const [sichtbar, setSichtbar] = useState(false);

  useEffect(() => {
    let abgebrochen = false;
    void ladeTourGesehen().then((gesehen) => {
      if (!abgebrochen) setSichtbar(!gesehen);
    });
    return () => { abgebrochen = true; };
  }, []);

  if (!sichtbar || !tour.available) return null;

  const spaeter = () => {
    void merkeTourGesehen(true);
    setSichtbar(false);
  };

  return (
    <div
      className="rounded-xl p-4 flex-1 flex items-start gap-3"
      style={{ backgroundColor: "var(--surface-dim)", border: "1px solid var(--border-soft)" }}
      data-tour="tour-invite"
    >
      <Compass size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0, marginTop: 2 }} />
      <div className="min-w-0 flex-1 self-stretch flex flex-col">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("inviteTitle")}</p>
        <p className="text-sm mt-1" style={{ color: "var(--foreground-soft)" }}>{t("inviteBody")}</p>
        <div className="flex items-stretch gap-2 mt-auto pt-3">
          <button
            type="button"
            onClick={() => void tour.start()}
            disabled={tour.busy}
            className="btn-primary text-sm rounded-lg px-4 py-2 disabled:opacity-50"
          >
            {tour.busy ? "…" : t("inviteStart")}
          </button>
          <button
            type="button"
            onClick={spaeter}
            className="text-sm rounded-lg px-3 py-2 text-foreground-soft border-2 border-border hover:border-kb transition-colors"
          >
            {t("dismiss")}
          </button>
        </div>
      </div>
    </div>
  );
}
