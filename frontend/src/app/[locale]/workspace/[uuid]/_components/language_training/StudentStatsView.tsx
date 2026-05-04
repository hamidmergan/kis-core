import { useEffect, useRef, useState } from "react";
import { ChartBar, ClockCounterClockwise } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import type { HeatmapDay, StudentStats } from "../../_types";
import { TOOL_COLORS } from "../../_constants";
import { RecentActivities } from "../studio/RecentActivities";
import { EmptyState } from "@/components/ui/EmptyState";

type StatsPeriod = "30" | "180";

interface DayDetail {
  day: string;
  sets: { set_id: number; tool: string; mode: string; title: string; answers: number; correct: number; wrong: number; first_answer: string | null; last_answer: string | null }[];
  total_answers: number;
  total_correct: number;
  total_wrong: number;
  chat_count: number;
}

export function StudentStatsView({ stats, loading, workspaceUuid, onNavigateToSet, language_trainingActive = true }: { stats: StudentStats | null; loading: boolean; workspaceUuid: string; onNavigateToSet?: (setId: number, tool: string, mode: string) => void; language_trainingActive?: boolean }) {
  const t = useTranslations("workspace.detail.languageTraining");
  const tTools = useTranslations("workspace.detail.langTools");
  const toolLabel = (tool: string) => tTools.has(tool) ? tTools(tool) : tool;
  const locale = useLocale();
  const dateLocale = locale === "en" ? "en-US" : "de-DE";
  const [period, setPeriod] = useState<StatsPeriod>("30");

  // Responsive heatmap: adjust cells to container width
  const observerRef = useRef<ResizeObserver | null>(null);
  const [heatmapContainerWidth, setHeatmapContainerWidth] = useState(0);
  const heatmapContainerRef = (el: HTMLDivElement | null) => {
    if (observerRef.current) { observerRef.current.disconnect(); observerRef.current = null; }
    if (el) {
      setHeatmapContainerWidth(el.clientWidth);
      const ro = new ResizeObserver(entries => {
        for (const e of entries) setHeatmapContainerWidth(e.contentRect.width);
      });
      ro.observe(el);
      observerRef.current = ro;
    }
  };
  useEffect(() => () => { observerRef.current?.disconnect(); }, []);

  // Heatmap source: language_training off -> learning tools only; otherwise combined.
  // Day-detail endpoint mirrors this choice via the category param.
  const heatmapSource: HeatmapDay[] = stats
    ? (language_trainingActive ? stats.heatmap : stats.lerntools_heatmap)
    : [];
  const dayCategoryParam = language_trainingActive ? "" : "&category=lerntools";

  const [selectedDay, setSelectedDay] = useState<HeatmapDay | null>(null);
  const [dayDetail, setDayDetail] = useState<DayDetail | null>(null);
  const [dayDetailLoading, setDayDetailLoading] = useState(false);

  useEffect(() => {
    if (!stats) return;
    const hasAnyActivity = heatmapSource.some(d => d.answers > 0);
    const entry = hasAnyActivity ? (heatmapSource.find(d => d.day === stats.today) ?? null) : null;
    setSelectedDay(entry);
    setDayDetail(null);
    if (entry && entry.answers > 0) {
      setDayDetailLoading(true);
      fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/stats/day?date=${entry.day}${dayCategoryParam}`, { credentials: "include" })
        .then(r => r.ok ? r.json() : null)
        .then(d => setDayDetail(d))
        .finally(() => setDayDetailLoading(false));
    }
  }, [stats, workspaceUuid, language_trainingActive]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Expand/collapse for day detail (limit to 10 entries) ──
  const DAY_DETAIL_LIMIT = 10;
  const [showAllSets, setShowAllSets] = useState(false);
  useEffect(() => { setShowAllSets(false); }, [selectedDay]);

  if (loading) return (
    <div className="flex-1 flex items-center justify-center p-4">
      <p className="text-sm" style={{ color: "var(--muted)" }}>{t("stats.loading")}</p>
    </div>
  );
  if (!stats) return (
    <div className="flex-1 flex items-center justify-center p-4">
      <EmptyState
        icon={<ChartBar size={32} weight="bold" />}
        text={t("stats.emptyData")}
      />
    </div>
  );

  const { today } = stats;

  // Filter heatmap by period
  const periodDays = parseInt(period);
  const filteredHeatmap = heatmapSource.slice(-periodDays);
  const periodAnswers = filteredHeatmap.reduce((s, d) => s + d.answers, 0);
  const periodCorrect = filteredHeatmap.reduce((s, d) => s + d.correct, 0);
  const periodWrong = filteredHeatmap.reduce((s, d) => s + d.wrong, 0);
  const periodActiveDays = filteredHeatmap.filter(d => d.answers > 0).length;
  const periodAccuracy = periodAnswers > 0 ? Math.round(periodCorrect / periodAnswers * 100) : 0;

  // Heatmap rendering: weeks as columns, days as rows (Mon-Sun)
  const heatmapWeeks: HeatmapDay[][] = [];
  let currentWeek: HeatmapDay[] = [];
  for (const d of filteredHeatmap) {
    const dow = new Date(d.day + "T12:00:00+02:00").getDay(); // 0=Sun
    const mondayIdx = dow === 0 ? 6 : dow - 1; // 0=Mon
    if (mondayIdx === 0 && currentWeek.length > 0) {
      heatmapWeeks.push(currentWeek);
      currentWeek = [];
    }
    currentWeek.push(d);
  }
  if (currentWeek.length > 0) heatmapWeeks.push(currentWeek);

  const maxAns = Math.max(...filteredHeatmap.map(d => d.answers), 1);

  const accent = "var(--kb)";
  const heatRgb = "var(--kb-rgb)";

  function heatColor(answers: number): string {
    if (answers === 0) return `rgba(${heatRgb},0.07)`;
    const intensity = Math.min(answers / maxAns, 1);
    if (intensity < 0.25) return `rgba(${heatRgb},0.20)`;
    if (intensity < 0.5) return `rgba(${heatRgb},0.40)`;
    if (intensity < 0.75) return `rgba(${heatRgb},0.60)`;
    return `rgba(${heatRgb},0.85)`;
  }

  function formatDay(dayStr: string) {
    const d = new Date(dayStr + "T12:00:00+02:00");
    return d.toLocaleDateString(dateLocale, { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Berlin" });
  }

  function formatTime(iso: string | null) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleTimeString(dateLocale, { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
  }

  async function selectDay(d: HeatmapDay) {
    if (selectedDay?.day === d.day) { setSelectedDay(null); setDayDetail(null); return; }
    setSelectedDay(d);
    setDayDetail(null);
    if (d.answers > 0) {
      setDayDetailLoading(true);
      try {
        const res = await fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/stats/day?date=${d.day}${dayCategoryParam}`, { credentials: "include" });
        if (res.ok) setDayDetail(await res.json());
      } catch { /* ignore */ }
      setDayDetailLoading(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-4">
      {/* ── Period selector + period summary ── */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">{t("stats.activity")}</h3>
          <div className="flex gap-1">
            {([["30", t("stats.period30")], ["180", t("stats.period180")]] as [StatsPeriod, string][]).map(([val, label]) => (
              <button
                key={val}
                type="button"
                onClick={() => setPeriod(val)}
                className="px-2 py-0.5 rounded text-xs font-medium transition-colors"
                style={{
                  backgroundColor: period === val ? accent : "transparent",
                  color: period === val ? "#fff" : "var(--muted)",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {periodAnswers === 0 ? (
          <EmptyState
            size="sm"
            icon={<ChartBar size={32} weight="bold" />}
            text={t("stats.noActivityRange")}
          />
        ) : (
          <>
            {/* Period summary line */}
            <div className="flex gap-3 mb-2 text-xs" style={{ color: "var(--muted)" }}>
              <span>{t("stats.activeDays", { count: periodActiveDays })}</span>
              <span>{t("stats.answersCount", { count: periodAnswers })}</span>
              {periodAnswers > 0 && <span>{t("stats.percentCorrect", { pct: periodAccuracy })}</span>}
            </div>

            {/* ── Heatmap ── */}
            {(() => {
              const gap = 4;
              const labelsColWidth = 22;
              const labelsMarginRight = 8;
              const padding = 8;
              const numWeeks = heatmapWeeks.length || 1;
              const maxCellSize = 56;
              const minCellSize = 36;
              const availableWidth = heatmapContainerWidth - labelsColWidth - labelsMarginRight - padding;
              const fitSize = numWeeks > 0
                ? Math.floor((availableWidth - (numWeeks - 1) * gap) / numWeeks)
                : maxCellSize;
              const cellSize = heatmapContainerWidth === 0
                ? maxCellSize
                : Math.max(minCellSize, Math.min(maxCellSize, fitSize));
              const showDayNums = cellSize >= 18;
              // Build month labels with correct column spans
              const monthLabels: { label: string; colSpan: number }[] = [];
              let prevMonth = -1;
              for (const week of heatmapWeeks) {
                const d = new Date(week[0].day + "T12:00:00+02:00");
                const m = d.getMonth();
                if (m !== prevMonth) {
                  monthLabels.push({ label: d.toLocaleDateString(dateLocale, { month: "short", timeZone: "Europe/Berlin" }), colSpan: 1 });
                  prevMonth = m;
                } else {
                  monthLabels[monthLabels.length - 1].colSpan++;
                }
              }
              const weekdayLabels = [
                t("stats.weekdays.mo"),
                t("stats.weekdays.tu"),
                t("stats.weekdays.we"),
                t("stats.weekdays.th"),
                t("stats.weekdays.fr"),
                t("stats.weekdays.sa"),
                t("stats.weekdays.su"),
              ];
              return (
                <div ref={heatmapContainerRef} className="p-1 w-full overflow-x-auto">
                  <div className="flex mx-auto" style={{ width: "fit-content" }}>
                    {/* Row labels — fixed */}
                    <div className="flex flex-col flex-shrink-0" style={{ paddingTop: cellSize + gap + 2, width: labelsColWidth, marginRight: labelsMarginRight }}>
                      {weekdayLabels.map(d => (
                        <div key={d} className="flex items-center justify-end text-[10px] font-medium" style={{ height: cellSize, marginBottom: gap, color: "var(--muted)" }}>{d}</div>
                      ))}
                    </div>
                    {/* Grid with month headers */}
                    <div>
                      {/* Month labels */}
                      <div className="flex" style={{ marginBottom: gap, width: "fit-content" }}>
                        {monthLabels.map((m, i) => (
                          <div key={i} className="text-[10px] font-medium" style={{
                            width: m.colSpan * (cellSize + gap) - gap,
                            marginRight: gap,
                            color: "var(--muted)",
                            height: cellSize,
                            display: "flex",
                            alignItems: "center",
                          }}>{m.label}</div>
                        ))}
                      </div>
                      {/* Cells */}
                      <div className="flex" style={{ gap, width: "fit-content" }}>
                        {heatmapWeeks.map((week, wi) => (
                          <div key={wi} className="flex flex-col" style={{ gap }}>
                            {week.map(d => {
                              const isSelected = selectedDay?.day === d.day;
                              const dateObj = new Date(d.day + "T12:00:00+02:00");
                              const dayNum = dateObj.getDate();
                              const isToday = d.day === today;
                              const intensity = d.answers > 0 ? Math.min(d.answers / maxAns, 1) : 0;
                              const isDarkBg = intensity >= 0.5;
                              return (
                                <button
                                  key={d.day}
                                  type="button"
                                  onClick={() => selectDay(d)}
                                  className={`heatmap-cell rounded-[4px] transition-all flex items-center justify-center${isSelected ? " is-selected" : ""}`}
                                  style={{
                                    width: cellSize,
                                    height: cellSize,
                                    backgroundColor: heatColor(d.answers),
                                    outline: isSelected ? `2px solid ${accent}` : `0 solid var(--kb)`,
                                    outlineOffset: 1,
                                    borderBottom: isToday && !isSelected ? "2.5px solid var(--muted)" : "none",
                                  }}
                                  title={t("stats.answersTooltip", { date: formatDay(d.day), count: d.answers })}
                                >
                                  {showDayNums && <span className="text-[10px] font-medium" style={{ color: isDarkBg ? "#fff" : "var(--muted)" }}>{dayNum}</span>}
                                </button>
                              );
                            })}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Legend */}
            <div className="flex items-center justify-center gap-2 mt-2">
              <span className="text-[10px]" style={{ color: "var(--muted)" }}>{t("stats.less")}</span>
              {[0, 0.25, 0.5, 0.75, 1].map((v, i) => (
                <div key={i} className="rounded-[3px]" style={{ width: 14, height: 14, backgroundColor: v === 0 ? `rgba(${heatRgb},0.07)` : `rgba(${heatRgb},${0.15 + v * 0.70})` }} />
              ))}
              <span className="text-[10px]" style={{ color: "var(--muted)" }}>{t("stats.more")}</span>
            </div>
          </>
        )}
      </div>

      {/* ── Selected day detail ── */}
      {selectedDay && (
        <div className="rounded-xl p-3">
          <div className="mb-2">
            <div className="text-xs font-semibold" style={{ color: "var(--foreground)" }}>
              {formatDay(selectedDay.day)} {selectedDay.day === today && t("stats.today")}
            </div>
          </div>
          {selectedDay.answers === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-4" style={{ color: "var(--muted)" }}>
              <ClockCounterClockwise size={24} weight="bold" />
              <span className="text-xs text-center">{t("stats.noActivityDay")}</span>
            </div>
          ) : dayDetailLoading ? (
            <p className="text-xs" style={{ color: "var(--muted)" }}>{t("common.loading")}</p>
          ) : dayDetail ? (
            <div className="space-y-2">
              {/* Per-set breakdown */}
              {(showAllSets ? dayDetail.sets : dayDetail.sets.slice(0, DAY_DETAIL_LIMIT)).map(s => {
                const pct = s.answers > 0 ? Math.round(s.correct / s.answers * 100) : 0;
                // Clean title: remove file extensions for display
                const displayTitle = s.title.replace(/\.(pdf|mp4|mp3|webm|wav|m4a|ogg)$/i, "");
                return (
                  <div key={s.set_id} className="rounded-lg px-2.5 py-2 cursor-pointer transition-colors hover:bg-[var(--surface-dim)]" style={{ backgroundColor: "var(--surface)" }} onClick={() => onNavigateToSet?.(s.set_id, s.tool, s.mode)}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium truncate" style={{ color: "var(--foreground)", maxWidth: "70%" }}>
                        {displayTitle}
                      </span>
                      <span className="text-xs font-semibold" style={{ color: pct >= 70 ? accent : "var(--muted)" }}>
                        {pct}%
                      </span>
                    </div>
                    {/* Mini progress bar */}
                    <div className="flex rounded-full overflow-hidden" style={{ height: 4, backgroundColor: "var(--border)" }}>
                      <div style={{ width: `${pct}%`, backgroundColor: accent }} />
                      {s.wrong > 0 && <div style={{ width: `${100 - pct}%`, backgroundColor: "var(--border)" }} />}
                    </div>
                    <div className="flex items-center justify-between mt-1 text-[9px]" style={{ color: "var(--muted)" }}>
                      <span className="px-1 py-0.5 rounded" style={{
                        backgroundColor: (TOOL_COLORS[s.tool] || { bg: "var(--surface)" }).bg,
                        color: (TOOL_COLORS[s.tool] || { color: "var(--muted)" }).color,
                      }}>
                        {toolLabel(s.tool)}
                      </span>
                      <span>{t("stats.setCorrectFraction", { correct: s.correct, total: s.correct + s.wrong })}</span>
                    </div>
                  </div>
                );
              })}
              {dayDetail.sets.length > DAY_DETAIL_LIMIT && (
                <button
                  type="button"
                  onClick={() => setShowAllSets(v => !v)}
                  className="w-full text-[11px] font-medium py-2 rounded-lg transition-colors hover:bg-[var(--surface-dim)] hover:text-kb"
                  style={{ color: "var(--muted)", backgroundColor: "var(--surface)" }}
                >
                  {showAllSets ? t("stats.showLess") : t("stats.showMore", { count: dayDetail.sets.length - DAY_DETAIL_LIMIT })}
                </button>
              )}
            </div>
          ) : null}
        </div>
      )}

    </div>
  );
}
