"use client";

/**
 * Zahlen zu den globalen Werkzeugen.
 *
 * Die Quelle ist der Zaehler und nicht die Auftragstabelle: aus der faellt pro
 * Nutzer alles ueber dem Vorrat wieder heraus, eine Statistik daraus waere eine
 * ueber die Reste.
 */

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
  // Die Farbskala haengt am hoechsten je gesehenen Wert, damit ein Wechsel des
  // Zeitraums das Bild sichtbar heller oder dunkler macht.
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
