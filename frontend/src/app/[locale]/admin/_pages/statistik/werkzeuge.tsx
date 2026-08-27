"use client";

/** Numbers for the global tools, from the counter instead of the job table. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Balken, Kachel, Karte, Ladeanzeige } from "./_bausteine";
import { Raster, ZeitraumChips } from "./_raster";

interface Daten {
  range: string;
  totals: { jobs: number };
  per_tool: { tool: string; jobs: number }[];
  heat: number[][];
}

export default function StatistikWerkzeugePage() {
  const t = useTranslations("admin.statistik");
  const [daten, setDaten] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState(false);
  const [zeitraum, setZeitraum] = useState("alles");
  // The colour scale hangs off the highest value ever seen.
  const [skala, setSkala] = useState(1);

  useEffect(() => {
    fetch(`/api/admin/stats/tools?range=${zeitraum}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: Daten) => {
        setDaten(d);
        setSkala((alt) => Math.max(alt, ...d.heat.flat(), 1));
      })
      .catch(() => setFehler(true));
  }, [zeitraum]);

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!daten) return <Ladeanzeige />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kachel titel={t("tools.jobs")} wert={daten.totals.jobs} />
      </div>

      <Karte titel={t("tools.perTool")} hinweis={t("tools.perToolHint")}>
        <Balken
          zeilen={daten.per_tool.map((w) => ({
            label: t(`tools.names.${w.tool}`),
            wert: w.jobs,
          }))}
          kopf={[t("tools.colJobs")]}
        />
      </Karte>

      <Karte titel={t("heat.title")} hinweis={t("heat.hint")}>
        <ZeitraumChips wert={zeitraum} setzen={setZeitraum} />
        <Raster werte={daten.heat} einheit={t("heat.unitJobs")} max={skala} />
      </Karte>
    </div>
  );
}
