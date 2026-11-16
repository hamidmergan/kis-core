"use client";

import { useTranslations } from "next-intl";
import FarbWahl from "./FarbWahl";

interface Props {
  groups: { key: string; title: string; color: string }[];
  /** Missing until the colours arrive, the squares then cannot be changed. */
  palette: string[] | undefined;
  hiddenGroups: ReadonlySet<string>;
  onPickColor: (group: string, index: number) => void;
  onToggleGroup: (group: string) => void;
}

/** The workspaces of the month with their colour, a click on the name hides or shows one. */
export default function ScheduleMonthLegend({ groups, palette, hiddenGroups, onPickColor, onToggleGroup }: Props) {
  const t = useTranslations("schedule");
  if (groups.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
      {groups.map(({ key, title, color }) => {
        const aus = hiddenGroups.has(key);
        return (
          <span key={key} className="inline-flex items-center gap-1.5">
            {palette ? (
              <FarbWahl
                color={color}
                palette={palette}
                name={title}
                dimmed={aus}
                onPick={(i) => onPickColor(key, i)}
              />
            ) : (
              <span className="rounded-sm" style={{ width: 14, height: 14, backgroundColor: color }} />
            )}
            <button
              type="button"
              onClick={() => onToggleGroup(key)}
              aria-pressed={!aus}
              title={t(aus ? "month.showInCalendar" : "month.hideInCalendar")}
              className="text-xs cursor-pointer"
              style={{
                color: aus ? "var(--muted)" : "var(--foreground-soft)",
                textDecoration: aus ? "line-through" : undefined,
              }}
            >
              {title}
            </button>
          </span>
        );
      })}
    </div>
  );
}
