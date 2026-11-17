"use client";

/** Everything about one person, their jobs reach only as far as their pool. */

import { useTranslations } from "next-intl";
import { Balken, Karte, KleineZahl, Ladeanzeige } from "./_bausteine";
import { useStatistik } from "./_laden";
import { VerlaufAnsicht } from "./_verlauf";

interface Detail {
  id: number;
  name: string;
  role: string;
  level: string | null;
  since: string | null;
  last_seen: string | null;
  present_days: number;
  totals: { jobs: number; answered: number; chat: number };
  tools: { tool: string; jobs: number }[];
  modules: { title: string; uuid: string; role: string; answered: number; chat: number }[];
  recent: { tool: string; status: string; when: string | null }[];
}

function Marke({ text }: { text: string }) {
  return (
    <span className="rounded-full bg-surface-dim px-2 py-0.5 text-2xs font-semibold text-muted">
      {text}
    </span>
  );
}

export function PersonAnsicht({ id }: { id: number }) {
  const t = useTranslations("admin.statistik");
  const { daten: d, fehler } = useStatistik<Detail>(`/api/admin/stats/users/${id}`);

  if (fehler) return <p className="mt-4 text-sm text-error">{t("loadError")}</p>;
  if (!d) return <div className="mt-4"><Ladeanzeige /></div>;

  return (
    <div className="mt-4 space-y-4">
      <div className="rounded-xl border border-border-soft bg-background p-5">
        <div className="flex flex-wrap items-baseline gap-2.5">
          <h3 className="text-lg font-bold tracking-tight">{d.name}</h3>
          <Marke text={d.role} />
          {d.level && <Marke text={t("detail.level", { level: d.level })} />}
          <span className="text-xs text-muted">
            {t("detail.sinceLast", {
              since: d.since ?? "—",
              last: d.last_seen ?? t("detail.never"),
              days: d.present_days,
            })}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <KleineZahl titel={t("detail.jobs")} wert={d.totals.jobs} />
          <KleineZahl titel={t("detail.answered")} wert={d.totals.answered} />
          <KleineZahl titel={t("detail.chat")} wert={d.totals.chat} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Karte titel={t("detail.tools")} hinweis={t("detail.toolsHint")}>
          <Balken
            zeilen={d.tools.map((w) => ({ label: w.tool, wert: w.jobs }))}
            labelBreite={150}
          />
        </Karte>

        <Karte titel={t("detail.modules")}>
          {d.modules.length === 0 ? (
            <p className="mt-3 text-xs text-muted-soft">{t("detail.noModules")}</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-2xs uppercase text-muted">
                    <th className="py-2 pr-4">{t("assistant.colModule")}</th>
                    <th className="py-2 pr-4">{t("detail.colRole")}</th>
                    <th className="py-2 pr-4 text-right">{t("assistant.colAnswered")}</th>
                    <th className="py-2 text-right">{t("assistant.colChat")}</th>
                  </tr>
                </thead>
                <tbody>
                  {d.modules.map((m) => (
                    <tr key={m.uuid} className="border-b border-border-soft last:border-0">
                      <td className="py-2 pr-4 text-foreground-soft">{m.title}</td>
                      <td className="py-2 pr-4 text-muted">
                        {m.role === "owner" ? t("detail.roleOwner") : t("detail.roleMember")}
                      </td>
                      <td className="py-2 pr-4 text-right tabular-nums">
                        {m.answered.toLocaleString("de-DE")}
                      </td>
                      <td className="py-2 text-right tabular-nums text-muted">
                        {m.chat.toLocaleString("de-DE")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Karte>
      </div>

      <Karte titel={t("detail.recent")} hinweis={t("detail.recentHint")}>
        {d.recent.length === 0 ? (
          <p className="mt-3 text-xs text-muted-soft">{t("detail.noJobs")}</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-soft text-left text-2xs uppercase text-muted">
                  <th className="py-2 pr-4">{t("assistant.colTool")}</th>
                  <th className="py-2 text-right">{t("detail.colWhen")}</th>
                </tr>
              </thead>
              <tbody>
                {d.recent.map((j, i) => (
                  <tr key={i} className="border-b border-border-soft last:border-0">
                    <td className="py-2 pr-4 text-foreground-soft">{j.tool}</td>
                    <td className="py-2 text-right text-muted-soft">
                      {j.when ? new Date(j.when).toLocaleString("de-DE") : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Karte>

      <VerlaufAnsicht id={id} />
    </div>
  );
}
