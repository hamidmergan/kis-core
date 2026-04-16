import { useEffect, useRef, useState } from "react";
import { ChartBar, ClockCounterClockwise } from "@phosphor-icons/react";
import type { HeatmapDay, StudentStats } from "../_types";
import { TOOL_COLORS, TOOL_LABELS } from "../_constants";
import { RecentActivities } from "./RecentActivities";
import { StudioTabs } from "./StudioTabs";

type StatsPeriod = "30" | "180";

interface DayDetail {
  day: string;
  sets: { set_id: number; tool: string; mode: string; title: string; answers: number; correct: number; wrong: number; first_answer: string | null; last_answer: string | null }[];
  total_answers: number;
  total_correct: number;
  total_wrong: number;
  chat_count: number;
}

export function StudentStatsView({ stats, loading, moduleUuid, onNavigateToSet, sprachtrainingActive = true }: { stats: StudentStats | null; loading: boolean; moduleUuid: string; onNavigateToSet?: (setId: number, tool: string, mode: string) => void; sprachtrainingActive?: boolean }) {
  const [period, setPeriod] = useState<StatsPeriod>("30");
  const [category, setCategory] = useState<"lerntools" | "sprachtraining">("lerntools");

  // Responsive heatmap: Zellen an Containerbreite anpassen
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

  useEffect(() => {
    if (!sprachtrainingActive && category === "sprachtraining") setCategory("lerntools");
  }, [sprachtrainingActive, category]);

  // ── Lerntools: eigener State ──
  const [selDayLt, setSelDayLt] = useState<HeatmapDay | null>(null);
  const [detailLt, setDetailLt] = useState<DayDetail | null>(null);
  const [loadLt, setLoadLt] = useState(false);

  useEffect(() => {
    if (!stats) return;
    const hasAnyActivity = stats.lerntools_heatmap.some(d => d.answers > 0);
    const entry = hasAnyActivity ? (stats.lerntools_heatmap.find(d => d.day === stats.today) ?? null) : null;
    setSelDayLt(entry);
    setDetailLt(null);
    if (entry && entry.answers > 0) {
      setLoadLt(true);
      fetch(`/api/ki-assistent/modules/${moduleUuid}/stats/day?date=${entry.day}&category=lerntools`, { credentials: "include" })
        .then(r => r.ok ? r.json() : null)
        .then(d => setDetailLt(d))
        .finally(() => setLoadLt(false));
    }
  }, [stats, moduleUuid]);

  // ── Sprachtraining: eigener State ──
  const [selDaySt, setSelDaySt] = useState<HeatmapDay | null>(null);
  const [detailSt, setDetailSt] = useState<DayDetail | null>(null);
  const [loadSt, setLoadSt] = useState(false);

  useEffect(() => {
    if (!stats) return;
    const hasAnyActivity = stats.sprachtraining_heatmap.some(d => d.answers > 0);
    const entry = hasAnyActivity ? (stats.sprachtraining_heatmap.find(d => d.day === stats.today) ?? null) : null;
    setSelDaySt(entry);
    setDetailSt(null);
    if (entry && entry.answers > 0) {
      setLoadSt(true);
      fetch(`/api/ki-assistent/modules/${moduleUuid}/stats/day?date=${entry.day}&category=sprachtraining`, { credentials: "include" })
        .then(r => r.ok ? r.json() : null)
        .then(d => setDetailSt(d))
        .finally(() => setLoadSt(false));
    }
  }, [stats, moduleUuid]);

  // ── Aktive Kategorie ──
  const selectedDay = category === "lerntools" ? selDayLt : selDaySt;
  const dayDetail = category === "lerntools" ? detailLt : detailSt;
  const dayDetailLoading = category === "lerntools" ? loadLt : loadSt;

  // ── Expand/Collapse für Day-Detail (Limit auf 10 Einträge) ──
  const DAY_DETAIL_LIMIT = 10;
  const [showAllSets, setShowAllSets] = useState(false);
  useEffect(() => { setShowAllSets(false); }, [selDayLt, selDaySt, category]);

  if (loading) return (
    <div className="flex-1 flex items-center justify-center p-4">
      <p className="text-sm" style={{ color: "var(--muted)" }}>Statistik wird geladen…</p>
    </div>
  );
  if (!stats) return (
    <div className="flex-1 flex items-center justify-center p-4">
      <p className="text-sm" style={{ color: "var(--muted)" }}>Noch keine Daten vorhanden. Starte Übungen, um deine Statistik zu sehen.</p>
    </div>
  );

  const { lerntools, sprachtraining, lerntools_heatmap, sprachtraining_heatmap, chat, active_days, today } = stats;
  const currentOverview = category === "lerntools" ? lerntools : sprachtraining;
  const categoryHeatmap = category === "lerntools" ? lerntools_heatmap : sprachtraining_heatmap;

  // Filter heatmap by period
  const periodDays = parseInt(period);
  const filteredHeatmap = categoryHeatmap.slice(-periodDays);
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

  // Lerntools: brand blue, Sprachtraining: green
  const accent = category === "lerntools" ? "var(--kb)" : "#9333EA";
  const heatRgb = category === "lerntools" ? "0,66,97" : "147,51,234";

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
    return d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Berlin" });
  }

  function formatTime(iso: string | null) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
  }

  async function selectDay(d: HeatmapDay) {
    const setDay = category === "lerntools" ? setSelDayLt : setSelDaySt;
    const setDetail = category === "lerntools" ? setDetailLt : setDetailSt;
    const setLoad = category === "lerntools" ? setLoadLt : setLoadSt;
    if (selectedDay?.day === d.day) { setDay(null); setDetail(null); return; }
    setDay(d);
    setDetail(null);
    if (d.answers > 0) {
      setLoad(true);
      try {
        const res = await fetch(`/api/ki-assistent/modules/${moduleUuid}/stats/day?date=${d.day}&category=${category}`, { credentials: "include" });
        if (res.ok) setDetail(await res.json());
      } catch { /* ignore */ }
      setLoad(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-4">
      {/* ── Category filter ── */}
      {sprachtrainingActive && (
        <StudioTabs
          tabs={[
            { key: "lerntools", label: "Lerntools" },
            { key: "sprachtraining", label: "Fachsprachentraining" },
          ]}
          active={category}
          onSelect={(k) => setCategory(k as "lerntools" | "sprachtraining")}
          accentColor={category === "sprachtraining" ? "#9333EA" : undefined}
        />
      )}

      {/* ── Period selector + period summary ── */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">Aktivität</h3>
          <div className="flex gap-1">
            {([["30", "30 Tage"], ["180", "6 Monate"]] as [StatsPeriod, string][]).map(([val, label]) => (
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
          <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
            <ChartBar size={32} weight="light" />
            <span className="text-xs text-center">Noch keine Aktivitäten in diesem Zeitraum.</span>
          </div>
        ) : (
          <>
            {/* Period summary line */}
            <div className="flex gap-3 mb-2 text-xs" style={{ color: "var(--muted)" }}>
              <span>{periodActiveDays} aktive Tage</span>
              <span>{periodAnswers} Antworten</span>
              {periodAnswers > 0 && <span>{periodAccuracy}% richtig</span>}
            </div>

            {/* ── Heatmap ── */}
            {(() => {
              const gap = 4;
              const labelsColWidth = 22;
              const labelsMarginRight = 8;
              const padding = 8;
              const numWeeks = heatmapWeeks.length || 1;
              const maxCellSize = 32;
              const minCellSize = 14;
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
                  monthLabels.push({ label: d.toLocaleDateString("de-DE", { month: "short", timeZone: "Europe/Berlin" }), colSpan: 1 });
                  prevMonth = m;
                } else {
                  monthLabels[monthLabels.length - 1].colSpan++;
                }
              }
              return (
                <div ref={heatmapContainerRef} className="p-1 w-full">
                  <div className="flex mx-auto" style={{ width: "fit-content", maxWidth: "100%" }}>
                    {/* Row labels — fixed */}
                    <div className="flex flex-col flex-shrink-0" style={{ paddingTop: cellSize + gap + 2, width: labelsColWidth, marginRight: labelsMarginRight }}>
                      {["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map(d => (
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
                              return (
                                <button
                                  key={d.day}
                                  type="button"
                                  onClick={() => selectDay(d)}
                                  className="rounded-[4px] transition-all flex items-center justify-center"
                                  style={{
                                    width: cellSize,
                                    height: cellSize,
                                    backgroundColor: heatColor(d.answers),
                                    outline: isSelected ? `2px solid ${accent}` : "none",
                                    outlineOffset: 1,
                                    borderBottom: isToday && !isSelected ? `2.5px solid ${category === "sprachtraining" ? "#C084FC" : "var(--muted)"}` : "none",
                                  }}
                                  title={`${formatDay(d.day)}: ${d.answers} Antworten`}
                                >
                                  {showDayNums && <span className="text-[10px] font-medium" style={{ color: d.answers > 0 ? `rgba(255,255,255,${Math.min(0.5 + (d.answers / maxAns) * 0.5, 1)})` : "var(--muted)" }}>{dayNum}</span>}
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
              <span className="text-[10px]" style={{ color: "var(--muted)" }}>Weniger</span>
              {[0, 0.25, 0.5, 0.75, 1].map((v, i) => (
                <div key={i} className="rounded-[3px]" style={{ width: 14, height: 14, backgroundColor: v === 0 ? `rgba(${heatRgb},0.07)` : `rgba(${heatRgb},${0.15 + v * 0.70})` }} />
              ))}
              <span className="text-[10px]" style={{ color: "var(--muted)" }}>Mehr</span>
            </div>
          </>
        )}
      </div>

      {/* ── Selected day detail ── */}
      {selectedDay && (
        <div className="rounded-xl p-3">
          <div className="mb-2">
            <div className="text-xs font-semibold" style={{ color: "var(--text)" }}>
              {formatDay(selectedDay.day)} {selectedDay.day === today && "(Heute)"}
            </div>
          </div>
          {selectedDay.answers === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-4" style={{ color: "var(--muted)" }}>
              <ClockCounterClockwise size={24} weight="light" />
              <span className="text-xs text-center">Keine Aktivität an diesem Tag.</span>
            </div>
          ) : dayDetailLoading ? (
            <p className="text-xs" style={{ color: "var(--muted)" }}>Wird geladen…</p>
          ) : dayDetail ? (
            <div className="space-y-2">
              {/* Per-set breakdown */}
              {(showAllSets ? dayDetail.sets : dayDetail.sets.slice(0, DAY_DETAIL_LIMIT)).map(s => {
                const pct = s.answers > 0 ? Math.round(s.correct / s.answers * 100) : 0;
                // Clean title: remove file extensions for display
                const displayTitle = s.title.replace(/\.(pdf|mp4|mp3|webm|wav|m4a|ogg)$/i, "");
                return (
                  <div key={s.set_id} className="rounded-lg px-2.5 py-2 cursor-pointer transition-colors hover:brightness-95" style={{ backgroundColor: "var(--surface)" }} onClick={() => onNavigateToSet?.(s.set_id, s.tool, s.mode)}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium truncate" style={{ color: "var(--text)", maxWidth: "70%" }}>
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
                        {TOOL_LABELS[s.tool] || s.tool}
                      </span>
                      <span>{s.correct}/{s.correct + s.wrong} richtig</span>
                    </div>
                  </div>
                );
              })}
              {dayDetail.sets.length > DAY_DETAIL_LIMIT && (
                <button
                  type="button"
                  onClick={() => setShowAllSets(v => !v)}
                  className="w-full text-[11px] font-medium py-2 rounded-lg transition-opacity hover:opacity-70"
                  style={{ color: "var(--muted)", backgroundColor: "var(--surface)" }}
                >
                  {showAllSets ? "Weniger anzeigen" : `+${dayDetail.sets.length - DAY_DETAIL_LIMIT} weitere anzeigen`}
                </button>
              )}
            </div>
          ) : null}
        </div>
      )}

    </div>
  );
}

