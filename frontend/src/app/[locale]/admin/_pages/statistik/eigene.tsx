"use client";

/** A tab of its own instead of a filter, the server decides the modules. */

import React, { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import { Kachel, Karte, Ladeanzeige } from "./_bausteine";
import { ModulAnsicht } from "./_modul";
import { gruppiert, kopfBei } from "./_gruppen";

interface Modul {
  uuid: string;
  title: string;
  active: boolean;
  access: "owner" | "tutor";
  members: number;
  sources: number;
  chat: number;
  answered: number;
  last: string | null;
}

interface Daten {
  totals: { workspaces: number; members: number; chat: number; answered: number };
  workspaces: Modul[];
}

export default function StatistikEigenePage() {
  const t = useTranslations("admin.statistik");
  const [daten, setDaten] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState(false);
  const [modul, setModul] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/stats/eigene", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDaten)
      .catch(() => setFehler(true));
  }, []);

  // Before the cancellations and sorted once so everything sees the same order.
  const sortiert = useMemo(() => gruppiert(daten?.workspaces ?? []), [daten]);

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!daten) return <Ladeanzeige />;

  const eigene = daten.workspaces.filter((m) => m.access === "owner").length;
  const betreut = daten.totals.workspaces - eigene;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kachel
          titel={t("eigene.workspaces")}
          wert={daten.totals.workspaces}
          fuss={betreut > 0 ? t("eigene.ownAndTutored", { own: eigene, tutored: betreut }) : undefined}
        />
        <Kachel titel={t("assistant.colMembers")} wert={daten.totals.members} />
        <Kachel titel={t("assistant.chat")} wert={daten.totals.chat} />
        <Kachel titel={t("assistant.answered")} wert={daten.totals.answered} />
      </div>

      <Karte titel={t("eigene.modules")} hinweis={t("eigene.modulesHint")}>
        {daten.workspaces.length === 0 ? (
          <p className="mt-3 text-xs text-muted-soft">{t("eigene.none")}</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-soft text-left text-2xs text-muted uppercase whitespace-nowrap">
                  <th className="py-2 pr-4">{t("assistant.colModule")}</th>
                  <th className="py-2 pr-4 text-right">{t("assistant.colMembers")}</th>
                  <th className="py-2 pr-4 text-right">{t("assistant.colSources")}</th>
                  <th className="py-2 pr-4 text-right">{t("assistant.colChat")}</th>
                  <th className="py-2 pr-4 text-right">{t("assistant.colAnswered")}</th>
                  <th className="py-2 text-right">{t("assistant.colLast")}</th>
                </tr>
              </thead>
              <tbody>
                {sortiert.map((m, i) => {
                  const kopf = kopfBei(sortiert, i);
                  return (
                    <React.Fragment key={m.uuid}>
                      {kopf && (
                        <tr>
                          <th
                            colSpan={6}
                            scope="colgroup"
                            className="pt-5 pb-2 pr-4 text-left text-2xs font-semibold uppercase tracking-[0.07em] text-muted"
                          >
                            {kopf === "owner" ? t("eigene.groupOwned") : t("eigene.groupTutored")}
                          </th>
                        </tr>
                      )}
                      <tr
                        onClick={() => setModul(m.uuid)}
                        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setModul(m.uuid)}
                        tabIndex={0}
                        className="border-b border-border-soft hover:bg-surface cursor-pointer focus:outline-none focus-visible:bg-surface"
                      >
                        <td className="py-2 pr-4">
                          <span className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full shrink-0 ${m.active ? "bg-success-border" : "bg-border"}`} />
                            <span className="truncate max-w-50 text-foreground-soft">{m.title}</span>
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">{m.members}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{m.sources}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{m.chat.toLocaleString("de-DE")}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{m.answered.toLocaleString("de-DE")}</td>
                        <td className="py-2 text-right text-muted-soft whitespace-nowrap">
                          {m.last ? new Date(m.last).toLocaleDateString("de-DE") : "—"}
                        </td>
                      </tr>
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Karte>

      <Modal
        open={modul !== null}
        onClose={() => setModul(null)}
        title={daten.workspaces.find((m) => m.uuid === modul)?.title}
        size="xl"
      >
        {/* Der Weg mit Besitzpruefung, nicht der offene des Adminbereichs. */}
        {modul !== null && <ModulAnsicht uuid={modul} basis="/api/admin/stats/eigene" />}
      </Modal>
    </div>
  );
}
