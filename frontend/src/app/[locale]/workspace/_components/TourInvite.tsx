"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Compass } from "@phosphor-icons/react";
import { useRouter } from "@/i18n/navigation";
import { useDemoWorkspaces } from "./useDemoWorkspaces";
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
  const router = useRouter();
  const { items, join } = useDemoWorkspaces();
  const [sichtbar, setSichtbar] = useState(false);
  const [laeuft, setLaeuft] = useState(false);

  useEffect(() => {
    let abgebrochen = false;
    void ladeTourGesehen().then((gesehen) => {
      if (!abgebrochen) setSichtbar(!gesehen);
    });
    return () => { abgebrochen = true; };
  }, []);

  const kurs = items.find((m) => !m.owned);
  if (!sichtbar || !kurs) return null;

  const starten = async () => {
    setLaeuft(true);
    if (!kurs.joined) await join(kurs.uuid);
    // No mark on start: only the last step or "later" takes the invitation away.
    router.push(`/workspace/${kurs.uuid}?tour=1`);
  };

  const spaeter = () => {
    void merkeTourGesehen(true);
    setSichtbar(false);
  };

  return (
    <div
      className="rounded-xl p-4 mb-8 flex items-start gap-3"
      style={{ backgroundColor: "var(--surface-dim)", border: "1px solid var(--border-soft)" }}
      data-tour="tour-invite"
    >
      <Compass size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0, marginTop: 2 }} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("inviteTitle")}</p>
        <div className="flex items-center gap-2 mt-3">
          <button
            type="button"
            onClick={starten}
            disabled={laeuft}
            className="btn-primary text-sm rounded-lg px-4 py-2 disabled:opacity-50"
          >
            {laeuft ? "…" : t("inviteStart")}
          </button>
          <button
            type="button"
            onClick={spaeter}
            className="btn-ghost text-sm rounded-lg px-3 py-2 text-foreground-soft border border-border"
          >
            {t("dismiss")}
          </button>
        </div>
      </div>
    </div>
  );
}
