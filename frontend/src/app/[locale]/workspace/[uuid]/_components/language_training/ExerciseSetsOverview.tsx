import { Cards, DownloadSimple, Files, Sparkle, Trash } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { ExerciseSet, StudentStats } from "../../_types";
import { TOOL_LABELS } from "../../_constants";
import { SubviewHeader, type BreadcrumbItem, type ToolCategory } from "../layout/SubviewHeader";

export function ExerciseSetsOverview({
  title, toolKey, sets, onBack, onSelect, onCreate, onDelete, onDownload, sourceCount, stats, breadcrumbs, category,
}: {
  title: string; toolKey?: string; sets: ExerciseSet[];
  onBack: () => void; onSelect: (s: ExerciseSet) => void;
  onCreate: () => void; onDelete: (id: number) => void;
  onDownload?: (s: ExerciseSet) => void;
  sourceCount: number; stats?: StudentStats | null;
  breadcrumbs?: BreadcrumbItem[];
  category?: ToolCategory;
}) {

  const noSources = sourceCount === 0;
  const atLimit = sets.length >= 20;
  const isGenerating = sets.some((s) => s.status === "generating");
  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title={title} toolKey={toolKey} onBack={onBack} breadcrumbs={breadcrumbs} category={category} />
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        <div className="rounded-xl px-3 py-2 text-xs font-medium flex items-center gap-2"
          style={{
            color: noSources ? "var(--error-strong)" : sourceCount > 5 ? "#c4820e" : "var(--kb)",
          }}>
          <Files size={13} weight="bold" />
          {noSources
            ? "Keine Quelle ausgewählt"
            : sourceCount === 1
              ? "1 Quelle ausgewählt"
              : sourceCount <= 5
                ? `${sourceCount} Quellen ausgewählt`
                : `${sourceCount} Quellen vorhanden, es werden maximal 5 berücksichtigt`}
        </div>

        {sets.length === 0 ? (
          <EmptyState
            className="pt-[15%]"
            size="lg"
            icon={<Cards size={48} weight="bold" />}
            text="Wähle Quellen aus und drücke auf Erstellen."
            action={
              <button type="button" onClick={onCreate}
                disabled={noSources || atLimit || isGenerating}
                className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                <Sparkle size={12} weight="bold" /> {isGenerating ? "Wird generiert…" : `Erstellen (${sets.length}/20)`}
              </button>
            }
          />
        ) : (
          <>
            <div className="flex justify-center">
              <button type="button" onClick={onCreate}
                disabled={noSources || atLimit || isGenerating}
                className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                <Sparkle size={12} weight="bold" /> {isGenerating ? "Wird generiert…" : `Erstellen (${sets.length}/20)`}
              </button>
            </div>
            <div className="flex items-center justify-between px-1">
              <span className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>{sets.length} Übungen</span>
              <span className="text-xs" >{sets.reduce((s, e) => s + e.card_count, 0)} Karten</span>
            </div>
            <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
              {sets.map((s) => {
                const generating = s.status === "generating";
                const failed = s.status === "failed";
                const lastCorrect = s.last_run_correct ?? 0;
                const hasRun = (s.total_attempts ?? 0) > 0;
                return (
                  <div key={s.id} onClick={() => !generating && !failed && onSelect(s)}
                    className={`bg-background rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden group border-2 border-transparent transition-colors ${generating ? "opacity-70" : "cursor-pointer hover:border-[var(--kb)]"}`}
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    {/* Title + Score */}
                    <div className="flex items-start gap-2.5 flex-1 min-w-0">
                      <span className="text-sm font-semibold leading-snug flex-1 line-clamp-3 mt-0.5 kis-tooltip" style={{ color: "var(--foreground)" }}
                        data-tip={generating ? undefined : (s.title === "Wird generiert…" ? undefined : s.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, ""))}>
                        {generating ? "Wird generiert…" : (s.title === "Wird generiert…" ? (TOOL_LABELS[s.tool] || s.tool) : s.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, ""))}
                      </span>
                      {generating ? (
                        <Spinner size="sm" />
                      ) : failed ? (
                        <span className="shrink-0 text-xs font-bold" style={{ color: "var(--error)" }}>!</span>
                      ) : (() => {
                        const pct = hasRun ? Math.round((lastCorrect / s.card_count) * 100) : 0;
                        const r = 16; const c = 2 * Math.PI * r; const offset = c - (pct / 100) * c;
                        return (
                          <svg width="42" height="42" viewBox="0 0 42 42" className="shrink-0">
                            <circle cx="21" cy="21" r={r} fill="none" stroke="var(--border)" strokeWidth="3" />
                            <circle cx="21" cy="21" r={r} fill="none" stroke="var(--kb)" strokeWidth="3"
                              strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
                              transform="rotate(-90 21 21)" />
                            <text x="21" y="21" textAnchor="middle" dominantBaseline="central"
                              fontSize="10" fontWeight="700" fill="var(--kb)">{pct}%</text>
                          </svg>
                        );
                      })()}
                    </div>
                    {/* Bottom row: meta left, delete right */}
                    <div className="flex items-center justify-between mt-auto pt-1">
                      <span className="text-xs font-medium" >
                        {generating ? (s.mode === "glossary" ? "Glossar" : s.mode === "quiz" ? "Quiz" : s.mode === "lueckentext" ? "Lückentext" : s.mode === "vokabeltest" ? "Vokabeltest" : "Lernkarten") : failed ? "Fehlgeschlagen" : `${s.card_count} Karten`}
                        {!generating && s.mode === "glossary" && " · Glossar"}
                        {!generating && ` · ${new Date(s.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", timeZone: "Europe/Berlin" })}`}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {!generating && onDownload && (
                          <button type="button" onClick={(e) => { e.stopPropagation(); onDownload(s); }}
                            className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                            style={{ backgroundColor: "var(--surface-dim)" }}
                            title="Als Textdatei herunterladen">
                            <DownloadSimple size={12} />
                          </button>
                        )}
                        {!generating && <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                          className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                          style={{ backgroundColor: "var(--surface-dim)" }}
                          title="Löschen">
                          <Trash size={12} />
                        </button>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

