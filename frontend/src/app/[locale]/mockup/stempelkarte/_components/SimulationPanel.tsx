"use client";

import { useTranslations } from "next-intl";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import { useMockup } from "../../_lib/store";
import { EMPTY_CARD } from "../../_lib/types";
import { useText2 } from "../../_lib/useText2";
import { resizeStations } from "../_lib/stampLogic";

const COUNTS = [3, 4, 5, 6, 7, 8];
const SECONDARY =
  "px-4 py-2 text-sm rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-60";

/** Stands in for the QR scan and the admin while there is no backend, collapsed by default. */
export default function SimulationPanel({ onScan }: { onScan: (id: string) => void }) {
  const t = useTranslations("mockup.stamp.sim");
  const text = useText2();
  const [config, updateConfig] = useMockup("config");
  const [, updateCard] = useMockup("card");
  return (
    <CollapsibleCard title={t("heading")} description={t("hint")}>
      <div className="flex flex-col gap-5" data-testid="simulation">
        <div className="flex flex-wrap gap-2">
          {config.stations.map((station) => (
            <button
              key={station.id}
              type="button"
              onClick={() => onScan(station.id)}
              className={SECONDARY}
              data-testid={`sim-scan-${station.id}`}
            >
              {t("scan", { station: text(station.name) })}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-foreground-soft">{t("count")}</span>
          <div className="flex flex-wrap gap-2">
            {COUNTS.map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => updateConfig((c) => ({ ...c, stations: resizeStations(c.stations, n) }))}
                className={`px-3.5 py-2 rounded-full text-xs font-semibold border transition-all whitespace-nowrap ${
                  config.stations.length === n
                    ? "bg-kb text-white border-kb"
                    : "bg-background text-foreground-soft border-border hover:border-kb"
                }`}
                data-testid={`sim-count-${n}`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => updateCard(() => EMPTY_CARD)} className={SECONDARY} data-testid="sim-reset">
            {t("resetCard")}
          </button>
          <button
            type="button"
            onClick={() => updateCard({ lockUntil: null, failedAttempts: 0 })}
            className={SECONDARY}
            data-testid="sim-unlock"
          >
            {t("unlock")}
          </button>
        </div>
      </div>
    </CollapsibleCard>
  );
}
