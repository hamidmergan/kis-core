"use client";

/**
 * Zahlen zum KI-Assistenten.
 *
 * Die sieben Werkzeuge stehen in zwei Gruppen, wie die Kacheln im Modul.
 */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
// Dieselbe Blaetterleiste wie unter Meine Jobs, damit die Knoepfe im ganzen
// Haus gleich aussehen.
import { Pagination } from "@/app/[locale]/my-jobs/_components/Pagination";
import { Balken, Kachel, Karte, Ladeanzeige } from "./_bausteine";
import { Raster, ZeitraumChips } from "./_raster";
import { ModulAnsicht } from "./_modul";

interface Werkzeug { tool: string; count: number }
interface Modul {
  uuid: string; title: string; owner: string; active: boolean;
  sources: number; members: number; created: number; answered: number;
  chat: number; last: string | null;
}
interface Daten {
  totals: { workspaces: number; answered: number; chat: number };
  levels: { level: string; users: number }[];
  materials: { rows: { kind: string; count: number; chunks: number }[]; total: { count: number; chunks: number } };
  tools: { source: Werkzeug[]; glossary: Werkzeug[] };
  heat: number[][];
  workspaces: Modul[];
}

function Gruppe({ titel, zeilen }: { titel: string; zeilen: Werkzeug[] }) {
  const kachel = useTranslations("workspace.detail.studio.tiles");
  return (
    <>
      <p className="text-2xs font-semibold uppercase tracking-[0.08em] text-muted mt-5">{titel}</p>
      <Balken
        zeilen={zeilen.map((w) => ({ label: kachel(w.tool), wert: w.count }))}
        labelBreite={140}
      />
    </>
  );
}

/** Wie viele Module eine Seite fasst. */
const PRO_SEITE = 15;

export default function StatistikAssistentPage() {
  const t = useTranslations("admin.statistik");
  const [daten, setDaten] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState(false);
  const [modul, setModul] = useState<string | null>(null);
  const [zeitraum, setZeitraum] = useState("alles");
  const [ab, setAb] = useState(0);

  useEffect(() => {
    fetch("/api/admin/stats/assistant", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDaten)
      .catch(() => setFehler(true));
  }, []);

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!daten) return <Ladeanzeige />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Kachel titel={t("assistant.workspaces")} wert={daten.totals.workspaces} />
        <Kachel titel={t("assistant.answered")} wert={daten.totals.answered} />
        <Kachel titel={t("assistant.chat")} wert={daten.totals.chat} />
      </div>

      <Karte titel={t("assistant.levels")} hinweis={t("assistant.levelsHint")}>
        <Balken
          zeilen={daten.levels.map((s, i) => ({
            label: s.level,
            wert: s.users,
            // A1 bis C2 ist eine Reihenfolge, keine sechs gleichrangigen Dinge.
            farbe: ["fill-kb/25", "fill-kb/40", "fill-kb/55", "fill-kb/70", "fill-kb/85", "fill-kb"][i],
          }))}
          labelBreite={40}
        />
      </Karte>

      <Karte titel={t("heat.title")} hinweis={t("heat.hintAssistant")}>
        <ZeitraumChips wert={zeitraum} setzen={setZeitraum} />
        <Raster
          werte={daten.heat}
          einheit={t("heat.unitRequests")}
          max={Math.max(...daten.heat.flat(), 1)}
        />
      </Karte>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Karte titel={t("assistant.materials")} hinweis={t("assistant.materialsHint")}>
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-soft text-left text-2xs text-muted uppercase">
                  <th className="py-2 pr-4">{t("assistant.colKind")}</th>
                  <th className="py-2 pr-4 text-right">{t("assistant.colCount")}</th>
                  <th className="py-2 text-right">{t("assistant.colChunks")}</th>
                </tr>
              </thead>
              <tbody>
                {daten.materials.rows.map((m) => (
                  <tr key={m.kind} className="border-b border-border-soft">
                    <td className="py-2 pr-4 text-foreground-soft">{m.kind}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{m.count.toLocaleString("de-DE")}</td>
                    <td className="py-2 text-right tabular-nums text-muted">{m.chunks.toLocaleString("de-DE")}</td>
                  </tr>
                ))}
                <tr className="font-semibold">
                  <td className="py-2 pr-4">{t("assistant.total")}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{daten.materials.total.count.toLocaleString("de-DE")}</td>
                  <td className="py-2 text-right tabular-nums">{daten.materials.total.chunks.toLocaleString("de-DE")}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Karte>

        <Karte titel={t("assistant.tools")} hinweis={t("assistant.toolsHint")}>
          <Gruppe titel={t("assistant.groupSource")} zeilen={daten.tools.source} />
          <Gruppe titel={t("assistant.groupGlossary")} zeilen={daten.tools.glossary} />
        </Karte>
      </div>

      <Karte titel={t("assistant.modules")} hinweis={t("assistant.modulesHint")}>
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-2xs text-muted uppercase whitespace-nowrap">
                <th className="py-2 pr-4">{t("assistant.colModule")}</th>
                <th className="py-2 pr-4">{t("assistant.colOwner")}</th>
                <th className="py-2 pr-4 text-right">{t("assistant.colSources")}</th>
                <th className="py-2 pr-4 text-right">{t("assistant.colMembers")}</th>
                <th className="py-2 pr-4 text-right">{t("assistant.colCreated")}</th>
                <th className="py-2 pr-4 text-right">{t("assistant.colAnswered")}</th>
                <th className="py-2 pr-4 text-right">{t("assistant.colChat")}</th>
                <th className="py-2 text-right">{t("assistant.colLast")}</th>
              </tr>
            </thead>
            <tbody>
              {daten.workspaces.slice(ab, ab + PRO_SEITE).map((m) => (
                <tr
                  key={m.uuid}
                  onClick={() => setModul(m.uuid)}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setModul(m.uuid)}
                  tabIndex={0}
                  className="border-b border-border-soft last:border-0 hover:bg-surface cursor-pointer focus:outline-none focus-visible:bg-surface"
                >
                  <td className="py-2 pr-4">
                    <span className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${m.active ? "bg-success-border" : "bg-border"}`} />
                      <span className="truncate max-w-50 text-foreground-soft">{m.title}</span>
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-muted whitespace-nowrap">{m.owner}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{m.sources}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{m.members}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{m.created.toLocaleString("de-DE")}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{m.answered.toLocaleString("de-DE")}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">{m.chat.toLocaleString("de-DE")}</td>
                  <td className="py-2 text-right text-muted-soft whitespace-nowrap">
                    {m.last ? new Date(m.last).toLocaleDateString("de-DE") : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination
          total={daten.workspaces.length}
          offset={ab}
          limit={PRO_SEITE}
          onOffsetChange={setAb}
        />
      </Karte>

      <Modal
        open={modul !== null}
        onClose={() => setModul(null)}
        title={daten.workspaces.find((m) => m.uuid === modul)?.title}
        size="xl"
      >
        {modul !== null && <ModulAnsicht uuid={modul} />}
      </Modal>

    </div>
  );
}
