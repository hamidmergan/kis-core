"use client";

import React, { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CaretRight, ChartLineUp } from "@phosphor-icons/react";
import { EmptyState } from "@/components/ui/EmptyState";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";

interface KiTutorSummary {
  total_workspaces: number;
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

interface KiTutorWorkspaceStat {
  workspace_uuid: string;
  title: string;
  owner: string;
  is_active: boolean;
  source_count: number;
  enrollment_count: number;
  total_answers: number;
  accuracy: number;
  chat_messages: number;
  lecturer: { messages: number; exercises: number };
  students: KiTutorStudentStat[];
}

interface KiTutorStatsData {
  summary: KiTutorSummary;
  workspace_stats: KiTutorWorkspaceStat[];
  days: number;
}

type StatsMode = "source" | "glossary";

export default function KiTutorTab() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const labels = useWorkspaceLabel();
  const [data, setData] = useState<KiTutorStatsData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<StatsMode>("source");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const numLocale = locale === "en" ? "en-US" : "de-DE";
  const modeMeta: Record<StatsMode, { label: string; accent: string }> = {
    source: { label: t("kiTutor.modeSource"), accent: "var(--kb)" },
    glossary: { label: t("kiTutor.modeGlossary"), accent: "var(--kb)" },
  };

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

  if (loading && !data) return <p className="text-sm text-muted">{t("loading")}</p>;
  if (!data) return <p className="text-sm text-error">{t("loadError")}</p>;

  const accent = modeMeta[mode].accent;
  const periodLabel = (d: number) =>
    d === 7 ? t("kiTutor.days7") : d === 30 ? t("kiTutor.month1") : d === 90 ? t("kiTutor.months3") : t("kiTutor.months6");

  return (
    <div className={`space-y-6 transition-opacity ${loading ? "opacity-50 pointer-events-none" : ""}`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1">
          {(["source", "glossary"] as StatsMode[]).map((m) => {
            const active = mode === m;
            const meta = modeMeta[m];
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
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${days === d ? "bg-kb text-white border-kb" : "border-border text-foreground-soft hover:border-kb hover:text-kb"}`}
            >
              {periodLabel(d)}
            </button>
          ))}
        </div>
      </div>

      {data.workspace_stats.length === 0 ? (
        <EmptyState
          size="lg"
          icon={<ChartLineUp size={40} weight="bold" />}
          text={t("kiTutor.empty")}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-background border border-border-soft rounded-lg p-4">
              <p className="text-xs text-muted uppercase tracking-wide">{labels.plural}</p>
              <p className="text-2xl font-bold text-foreground mt-1">{data.summary.total_workspaces}</p>
            </div>
            <div className="bg-background border border-border-soft rounded-lg p-4">
              <p className="text-xs text-muted uppercase tracking-wide">{t("kiTutor.summaryActiveStudents", { days })}</p>
              <p className="text-2xl font-bold text-foreground mt-1">{data.summary.active_students}</p>
            </div>
            <div className="bg-background border border-border-soft rounded-lg p-4">
              <p className="text-xs text-muted uppercase tracking-wide">{t("kiTutor.summaryExercises", { days })}</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {data.summary.total_answers.toLocaleString(numLocale)}
              </p>
            </div>
            <div className="bg-background border border-border-soft rounded-lg p-4">
              <p className="text-xs text-muted uppercase tracking-wide">{t("kiTutor.summaryChat", { days })}</p>
              <p className="text-2xl font-bold text-foreground mt-1">
                {data.summary.total_chat_messages.toLocaleString(numLocale)}
              </p>
            </div>
          </div>

          <div className="bg-background border border-border-soft rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-soft text-left text-xs text-muted uppercase">
                    <th className="px-4 py-2 w-6"></th>
                    <th className="px-4 py-2">{labels.singular}</th>
                    <th className="px-4 py-2">{t("kiTutor.colCreator")}</th>
                    <th className="px-4 py-2 text-right">{t("kiTutor.colSources")}</th>
                    <th className="px-4 py-2 text-right">{t("kiTutor.colParticipants")}</th>
                    <th className="px-4 py-2 text-right">{t("kiTutor.colExercises")}</th>
                    <th className="px-4 py-2 text-right">{t("kiTutor.colChat")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.workspace_stats.map((m) => {
                    const isOpen = expanded.has(m.workspace_uuid);
                    return (
                      <React.Fragment key={m.workspace_uuid}>
                        <tr
                          onClick={() => toggle(m.workspace_uuid)}
                          className={`border-b border-border-soft cursor-pointer transition-colors ${isOpen ? "bg-surface" : "hover:bg-surface"}`}
                        >
                          <td className="px-4 py-2 text-muted-soft">
                            <CaretRight size={12} weight="bold" className={`transition-transform ${isOpen ? "rotate-90" : ""}`} />
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={`w-2 h-2 rounded-full shrink-0 ${m.is_active ? "bg-success-border" : "bg-border"}`}
                              />
                              <span className="font-medium text-foreground-soft truncate max-w-50">
                                {m.title}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-2 text-foreground-soft">{m.owner}</td>
                          <td className="px-4 py-2 text-right text-foreground-soft">{m.source_count}</td>
                          <td className="px-4 py-2 text-right text-foreground-soft">{m.enrollment_count}</td>
                          <td className="px-4 py-2 text-right" style={{ color: accent }}>
                            {(m.total_answers + m.lecturer.exercises).toLocaleString(numLocale)}
                          </td>
                          <td className="px-4 py-2 text-right text-foreground-soft">
                            {(m.chat_messages + m.lecturer.messages).toLocaleString(numLocale)}
                          </td>
                        </tr>
                        {isOpen && (
                          <tr>
                            <td colSpan={7} className="px-0 py-0">
                              <div className="bg-surface border-t border-border-soft">
                                {m.students.length === 0 ? (
                                  <p className="px-8 py-3 text-xs text-muted-soft">
                                    {t("kiTutor.noStudents")}
                                  </p>
                                ) : (
                                  <table className="w-full text-xs">
                                    <thead>
                                      <tr className="text-left text-muted-soft uppercase">
                                        <th className="pl-12 pr-4 py-2">{t("kiTutor.colStudent")}</th>
                                        <th className="px-4 py-2 text-right">{t("kiTutor.colExercises")}</th>
                                        <th className="px-4 py-2 text-right">{t("kiTutor.colCorrect")}</th>
                                        <th className="px-4 py-2 text-right">{t("kiTutor.colLerntools")}</th>
                                        <th className="px-4 py-2 text-right">{t("kiTutor.colLanguageTraining")}</th>
                                        <th className="px-4 py-2 text-right">{t("kiTutor.colChat")}</th>
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
                                            {s.answers.toLocaleString(numLocale)}
                                          </td>
                                          <td className="px-4 py-2 text-right text-success">
                                            {s.correct.toLocaleString(numLocale)}
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
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
