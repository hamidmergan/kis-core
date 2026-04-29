"use client";

import React, { useEffect, useState } from "react";

interface KiTutorSummary {
  total_modules: number;
  active_students: number;
  total_answers: number;
  total_chat_messages: number;
}

interface KiTutorStudentStat {
  name: string;
  answers: number;
  correct: number;
  accuracy: number;
  lerntools: number;
  language_training: number;
  chat_messages: number;
}

interface KiTutorModuleStat {
  module_uuid: string;
  title: string;
  owner: string;
  is_active: boolean;
  source_count: number;
  enrollment_count: number;
  total_answers: number;
  accuracy: number;
  chat_messages: number;
  dozent: { messages: number; exercises: number };
  students: KiTutorStudentStat[];
}

interface KiTutorStatsData {
  summary: KiTutorSummary;
  module_stats: KiTutorModuleStat[];
  days: number;
}

type StatsMode = "quelle" | "glossary";
const MODE_META: Record<StatsMode, { label: string; accent: string }> = {
  quelle: { label: "Lerntools", accent: "var(--kb)" },
  glossary: { label: "Fachsprachentraining", accent: "var(--kb)" },
};

export default function KiTutorTab() {
  const [data, setData] = useState<KiTutorStatsData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<StatsMode>("quelle");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    setLoading(true);
    fetch(`/api/admin/ai-assistant/stats?days=${days}&mode=${mode}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setData(d))
      .finally(() => setLoading(false));
  }, [days, mode]);

  const toggle = (uuid: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(uuid)) next.delete(uuid);
      else next.add(uuid);
      return next;
    });

  if (loading && !data) return <p className="text-sm text-muted">Laden…</p>;
  if (!data) return <p className="text-sm text-error">Fehler beim Laden</p>;

  const accent = MODE_META[mode].accent;

  return (
    <div className={`space-y-6 transition-opacity ${loading ? "opacity-50 pointer-events-none" : ""}`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1">
          {(["quelle", "glossary"] as StatsMode[]).map((m) => {
            const active = mode === m;
            const meta = MODE_META[m];
            return (
              <button
                key={m}
                onClick={() => setMode(m)}
                className="px-4 py-1.5 text-xs font-medium rounded-full border transition-colors"
                style={
                  active
                    ? { backgroundColor: meta.accent, color: "#fff", borderColor: meta.accent }
                    : { borderColor: "var(--border)", color: "var(--muted)" }
                }
              >
                {meta.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${days === d ? "bg-kb text-white border-kb" : "border-border text-foreground-soft hover:border-muted"}`}
            >
              {d === 7 ? "7 Tage" : d === 30 ? "1 Monat" : d === 90 ? "3 Monate" : "6 Monate"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white border border-border-soft rounded-lg p-4">
          <p className="text-xs text-muted uppercase tracking-wide">Workspaces</p>
          <p className="text-2xl font-bold text-foreground mt-1">{data.summary.total_modules}</p>
        </div>
        <div className="bg-white border border-border-soft rounded-lg p-4">
          <p className="text-xs text-muted uppercase tracking-wide">Aktive Teilnehmer ({days}T)</p>
          <p className="text-2xl font-bold text-foreground mt-1">{data.summary.active_students}</p>
        </div>
        <div className="bg-white border border-border-soft rounded-lg p-4">
          <p className="text-xs text-muted uppercase tracking-wide">Übungen ({days}T)</p>
          <p className="text-2xl font-bold text-foreground mt-1">
            {data.summary.total_answers.toLocaleString("de-DE")}
          </p>
        </div>
        <div className="bg-white border border-border-soft rounded-lg p-4">
          <p className="text-xs text-muted uppercase tracking-wide">Chat ({days}T)</p>
          <p className="text-2xl font-bold text-foreground mt-1">
            {data.summary.total_chat_messages.toLocaleString("de-DE")}
          </p>
        </div>
      </div>

      <div className="bg-white border border-border-soft rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-xs text-muted uppercase">
                <th className="px-4 py-2 w-6"></th>
                <th className="px-4 py-2">Workspace</th>
                <th className="px-4 py-2">Ersteller</th>
                <th className="px-4 py-2 text-right">Quellen</th>
                <th className="px-4 py-2 text-right">Teilnehmer</th>
                <th className="px-4 py-2 text-right">Übungen</th>
                <th className="px-4 py-2 text-right">Chat</th>
              </tr>
            </thead>
            <tbody>
              {data.module_stats.map((m) => {
                const isOpen = expanded.has(m.module_uuid);
                return (
                  <React.Fragment key={m.module_uuid}>
                    <tr
                      onClick={() => toggle(m.module_uuid)}
                      className={`border-b border-border-soft cursor-pointer transition-colors ${isOpen ? "bg-surface" : "hover:bg-surface"}`}
                    >
                      <td className="px-4 py-2 text-muted-soft text-xs">{isOpen ? "▼" : "▶"}</td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full shrink-0 ${m.is_active ? "bg-success-border" : "bg-border"}`}
                          />
                          <span className="font-medium text-foreground-soft truncate max-w-[200px]">
                            {m.title}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-2 text-foreground-soft">{m.owner}</td>
                      <td className="px-4 py-2 text-right text-foreground-soft">{m.source_count}</td>
                      <td className="px-4 py-2 text-right text-foreground-soft">{m.enrollment_count}</td>
                      <td className="px-4 py-2 text-right" style={{ color: accent }}>
                        {(m.total_answers + m.dozent.exercises).toLocaleString("de-DE")}
                      </td>
                      <td className="px-4 py-2 text-right text-foreground-soft">
                        {(m.chat_messages + m.dozent.messages).toLocaleString("de-DE")}
                      </td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={7} className="px-0 py-0">
                          <div className="bg-surface border-t border-border-soft">
                            {m.students.length === 0 ? (
                              <p className="px-8 py-3 text-xs text-muted-soft">
                                Keine eingeschriebenen Teilnehmer
                              </p>
                            ) : (
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="text-left text-muted-soft uppercase">
                                    <th className="pl-12 pr-4 py-2">Student</th>
                                    <th className="px-4 py-2 text-right">Übungen</th>
                                    <th className="px-4 py-2 text-right">Richtig</th>
                                    <th className="px-4 py-2 text-right">Lerntools</th>
                                    <th className="px-4 py-2 text-right">Sprachtr.</th>
                                    <th className="px-4 py-2 text-right">Chat</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {m.students.map((s) => (
                                    <tr
                                      key={s.name}
                                      className="border-t border-border-soft hover:bg-surface/50"
                                    >
                                      <td className="pl-12 pr-4 py-2 text-foreground-soft">{s.name}</td>
                                      <td className="px-4 py-2 text-right text-foreground-soft">
                                        {s.answers.toLocaleString("de-DE")}
                                      </td>
                                      <td className="px-4 py-2 text-right text-success">
                                        {s.correct.toLocaleString("de-DE")}
                                      </td>
                                      <td className="px-4 py-2 text-right" style={{ color: "var(--kb)" }}>
                                        {s.lerntools}
                                      </td>
                                      <td className="px-4 py-2 text-right" style={{ color: "var(--kb)" }}>
                                        {s.language_training}
                                      </td>
                                      <td className="px-4 py-2 text-right text-foreground-soft">
                                        {s.chat_messages}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
              {data.module_stats.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-muted-soft">
                    Keine Workspaces vorhanden
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
