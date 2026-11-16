"use client";

import { useTranslations } from "next-intl";
import Checkbox from "@/components/ui/Checkbox";
import type { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import MaterialGauge, { MeasureError, MeasureNote } from "./MaterialGauge";

/** The sources of the chosen workspace as a checklist with the measure, capped at a maximum. */
export default function SourceChecklist({ namespace, sources, selectedIds, max, messung, onChange }: {
  namespace: "tools.podcast.content" | "tools.praesentation.content";
  sources: { uuid: string; filename: string }[];
  selectedIds: string[];
  max: number;
  messung: ReturnType<typeof useMaterialMeasure>;
  onChange: (ids: string[]) => void;
}) {
  const t = useTranslations(namespace);
  const voll = selectedIds.length >= max;
  const toggleSource = (uuid: string) => {
    const set = new Set(selectedIds);
    if (set.has(uuid)) set.delete(uuid);
    else if (!voll) set.add(uuid);
    onChange([...set]);
  };

  return (
    <div>
      {selectedIds.length > 0 && <MaterialGauge bilanz={messung} max={messung.max} />}
      <span className="block text-sm font-medium text-foreground-soft mb-2">{t("sourcesLabel")}</span>
      <ul className="space-y-2">
        {sources.map((s) => (
          <li key={s.uuid}>
            <div className="flex items-center justify-between gap-3">
              <Checkbox
                checked={selectedIds.includes(s.uuid)}
                disabled={voll && !selectedIds.includes(s.uuid)}
                onChange={() => toggleSource(s.uuid)}
                label={s.filename}
                labelClassName="text-sm text-foreground"
              />
              {selectedIds.includes(s.uuid) && <MeasureNote messung={messung.forSource(s.uuid)} />}
            </div>
            {selectedIds.includes(s.uuid) && <MeasureError messung={messung.forSource(s.uuid)} />}
          </li>
        ))}
      </ul>
      <p className={`mt-2 text-xs ${voll ? "text-error font-medium" : "text-muted"}`}>
        {t(voll ? "sourcesFull" : "sourcesHint", { max })}
      </p>
    </div>
  );
}
