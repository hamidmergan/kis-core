"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Toolbox } from "@phosphor-icons/react";
import { usePermissions } from "@/hooks/usePermissions";
import { ladeWerkzeugTourGesehen, merkeWerkzeugTourGesehen } from "@/components/tour/toolsTourSeen";

/**
 * Entry into the tour of the tools, on the start page.
 *
 * The second invitation next to the one for a course. It only stands while
 * there is something to show, so whoever has no tool at all never sees it, and
 * whoever walked the tour to its end or waved it off does not see it again,
 * while breaking off midway leaves it standing.
 *
 * Pressing start hands over to the sidebar, which is the only place that
 * survives the jumps from tool to tool, see useToolsTour.
 */
export function ToolsTourInvite() {
  const t = useTranslations("toolsTour");
  const { loaded, permissions } = usePermissions();
  const [sichtbar, setSichtbar] = useState(false);

  useEffect(() => {
    let abgebrochen = false;
    void ladeWerkzeugTourGesehen().then((gesehen) => {
      if (!abgebrochen) setSichtbar(!gesehen);
    });
    return () => { abgebrochen = true; };
  }, []);

  if (!sichtbar || !loaded || permissions.tools.length === 0) return null;

  const spaeter = () => {
    void merkeWerkzeugTourGesehen(true);
    setSichtbar(false);
  };

  return (
    <div
      className="rounded-xl p-4 flex-1 flex items-start gap-3"
      style={{ backgroundColor: "var(--surface-dim)", border: "1px solid var(--border-soft)" }}
      data-tour="tools-tour-invite"
    >
      <Toolbox size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0, marginTop: 2 }} />
      <div className="min-w-0 flex-1 self-stretch flex flex-col">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("inviteTitle")}</p>
        <p className="text-sm mt-1" style={{ color: "var(--foreground-soft)" }}>{t("inviteBody")}</p>
        <div className="flex items-stretch gap-2 mt-auto pt-3">
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event("tools-tour:start"))}
            className="btn-primary text-sm rounded-lg px-4 py-2"
          >
            {t("inviteStart")}
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
