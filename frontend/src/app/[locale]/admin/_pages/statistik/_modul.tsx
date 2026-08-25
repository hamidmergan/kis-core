"use client";

/**
 * Alles zu einem Modul an einer Stelle.
 *
 * Steht im Fenster, das eine Zeile der Modultabelle oeffnet. Die beiden Trainer
 * stehen getrennt, wie im Modul selbst, und erzeugt bleibt von beantwortet
 * getrennt: der Vorrat wird angelegt, danach arbeitet ihn jemand ab.
 */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Karte, Ladeanzeige } from "./_bausteine";

interface Werkzeug { tool: string; created: number; answered: number }
interface Detail {
  uuid: string;
  title: string;
  owner: string;
  active: boolean;
  since: string | null;
  last: string | null;
  totals: { members: number; sources: number; created: number; answered: number; chat: number };
  source_tools: Werkzeug[];
  glossary_tools: Werkzeug[];
  materials: { name: string; kind: string; chunks: number; status: string }[];
  members: { name: string; answered: number; chat: number }[];
}

function KleineZahl({ titel, wert }: { titel: string; wert: number }) {
  return (
    <div className="rounded-lg border border-border-soft px-3.5 py-3">
      <p className="text-2xs font-semibold uppercase tracking-[0.06em] text-muted">{titel}</p>
      <p className="mt-0.5 text-xl font-bold tabular-nums tracking-tight">
        {wert.toLocaleString("de-DE")}
      </p>
    </div>
  );
}

function TrainerTabelle({ zeilen, leer }: { zeilen: Werkzeug[]; leer: string }) {
  const t = useTranslations("admin.statistik");
  const kachel = useTranslations("workspace.detail.studio.tiles");
  if (zeilen.length === 0) return <p className="mt-3 text-xs text-muted-soft">{leer}</p>;
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-soft text-left text-2xs uppercase text-muted">
            <th className="py-2 pr-4">{t("assistant.colTool")}</th>
            <th className="py-2 pr-4 text-right">{t("assistant.colCreated")}</th>
            <th className="py-2 text-right">{t("assistant.colAnswered")}</th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((w) => (
            <tr key={w.tool} className="border-b border-border-soft last:border-0">
              <td className="py-2 pr-4 text-foreground-soft">{kachel(w.tool)}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{w.created.toLocaleString("de-DE")}</td>
              <td className="py-2 text-right tabular-nums text-muted">{w.answered.toLocaleString("de-DE")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ModulAnsicht({ uuid }: { uuid: string }) {
  const t = useTranslations("admin.statistik");
  const [d, setD] = useState<Detail | null>(null);
  const [fehler, setFehler] = useState(false);

  useEffect(() => {
    setD(null);
    setFehler(false);
    fetch(`/api/admin/stats/workspaces/${uuid}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setD)
      .catch(() => setFehler(true));
  }, [uuid]);

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!d) return <Ladeanzeige />;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border-soft bg-background p-5">
        <div className="flex flex-wrap items-baseline gap-2.5">
          <span className="rounded-full bg-surface-dim px-2 py-0.5 text-2xs font-semibold text-muted">
            {d.active ? t("detail.active") : t("detail.inactive")}
          </span>
          <span className="text-xs text-muted">
            {t("detail.ownerSince", { owner: d.owner, since: d.since ?? "—" })}
            {d.last ? ` · ${t("detail.lastUsed", { date: new Date(d.last).toLocaleDateString("de-DE") })}` : ""}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <KleineZahl titel={t("assistant.colMembers")} wert={d.totals.members} />
          <KleineZahl titel={t("assistant.materials")} wert={d.totals.sources} />
          <KleineZahl titel={t("assistant.colCreated")} wert={d.totals.created} />
          <KleineZahl titel={t("assistant.colAnswered")} wert={d.totals.answered} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Karte titel={t("assistant.groupSource")} hinweis={t("detail.sourceHint")}>
          <TrainerTabelle zeilen={d.source_tools} leer={t("assistant.groupEmpty")} />
        </Karte>
        <Karte titel={t("assistant.groupGlossary")}>
          <TrainerTabelle zeilen={d.glossary_tools} leer={t("detail.trainerOff")} />
        </Karte>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Karte titel={t("assistant.materials")}>
          {d.materials.length === 0 ? (
            <p className="mt-3 text-xs text-muted-soft">{t("detail.noMaterials")}</p>
          ) : (
            <div className="mt-4 max-h-72 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-background">
                  <tr className="border-b border-border-soft text-left text-2xs uppercase text-muted">
                    <th className="py-2 pr-4">{t("detail.colFile")}</th>
                    <th className="py-2 pr-4">{t("assistant.colKind")}</th>
                    <th className="py-2 pr-4 text-right">{t("assistant.colChunks")}</th>
                    <th className="py-2 text-right">{t("detail.colState")}</th>
                  </tr>
                </thead>
                <tbody>
                  {d.materials.map((m, i) => (
                    <tr key={i} className="border-b border-border-soft">
                      <td className="py-2 pr-4 max-w-60 truncate text-foreground-soft">{m.name}</td>
                      <td className="py-2 pr-4 text-muted uppercase">{m.kind}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{m.chunks.toLocaleString("de-DE")}</td>
                      <td className="py-2 text-right text-muted-soft">{m.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Karte>

        <Karte titel={t("detail.members")}>
          {d.members.length === 0 ? (
            <p className="mt-3 text-xs text-muted-soft">{t("detail.noMembers")}</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-2xs uppercase text-muted">
                    <th className="py-2 pr-4">{t("detail.colName")}</th>
                    <th className="py-2 pr-4 text-right">{t("assistant.colAnswered")}</th>
                    <th className="py-2 text-right">{t("assistant.colChat")}</th>
                  </tr>
                </thead>
                <tbody>
                  {d.members.map((p, i) => (
                    <tr key={i} className="border-b border-border-soft last:border-0">
                      <td className="py-2 pr-4 text-foreground-soft">{p.name}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{p.answered.toLocaleString("de-DE")}</td>
                      <td className="py-2 text-right tabular-nums text-muted">{p.chat.toLocaleString("de-DE")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Karte>
      </div>
    </div>
  );
}
