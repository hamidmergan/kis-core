import { Cards, DownloadSimple, Files, Sparkle, Trash } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { ExerciseSet, StudentStats } from "../../_types";
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
  const t = useTranslations("workspace.detail.languageTraining");
  const locale = useLocale();
  const dateLocale = locale === "en" ? "en-US" : "de-DE";

  const noSources = sourceCount === 0;
  const atLimit = sets.length >= 20;
  const isGenerating = sets.some((s) => s.status === "generating");
  const generatingLabel = t("common.generating");
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
            ? t("sourceStatus.none")
            : sourceCount === 1
              ? t("sourceStatus.one")
              : sourceCount <= 5
                ? t("sourceStatus.few", { count: sourceCount })
                : t("sourceStatus.many", { count: sourceCount })}
        </div>

        {sets.length === 0 ? (
          <EmptyState
            className="pt-[15%]"
            size="lg"
            icon={<Cards size={48} weight="bold" />}
            text={t("exerciseSets.emptyText")}
            action={
              <button type="button" onClick={onCreate}
                disabled={noSources || atLimit || isGenerating}
                className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                <Sparkle size={12} weight="bold" /> {isGenerating ? generatingLabel : t("exerciseSets.createButton", { current: sets.length, max: 20 })}
              </button>
            }
          />
        ) : (
          <>
            <div className="flex justify-center">
              <button type="button" onClick={onCreate}
                disabled={noSources || atLimit || isGenerating}
                className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                <Sparkle size={12} weight="bold" /> {isGenerating ? generatingLabel : t("exerciseSets.createButton", { current: sets.length, max: 20 })}
              </button>
            </div>
            <div className="flex items-center justify-between px-1">
              <span className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>{t("exerciseSets.exercisesCount", { count: sets.length })}</span>
              <span className="text-xs" >{t("exerciseSets.cardsCount", { count: sets.reduce((s, e) => s + e.card_count, 0) })}</span>
            </div>
            <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
              {sets.map((s) => {
                const generating = s.status === "generating";
                const failed = s.status === "failed";
                const lastCorrect = s.last_run_correct ?? 0;
                const hasRun = (s.total_attempts ?? 0) > 0;
                const modeLabel = (() => {
                  switch (s.mode) {
                    case "glossary": return t("exerciseSets.modeGlossary");
                    case "quiz": return t("exerciseSets.modeQuiz");
                    case "lueckentext": return t("exerciseSets.modeLueckentext");
                    case "vokabeltest": return t("exerciseSets.modeVokabeltest");
                    default: return t("exerciseSets.modeFlashcards");
                  }
                })();
                return (
                  <div key={s.id} onClick={() => !generating && !failed && onSelect(s)}
                    className={`bg-background rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden group border-2 border-transparent transition-colors ${generating ? "opacity-70" : "cursor-pointer hover:border-[var(--kb)]"}`}
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    {/* Title + Score */}
                    <div className="flex items-start gap-2.5 flex-1 min-w-0">
                      <span className="text-sm font-semibold leading-snug flex-1 line-clamp-3 mt-0.5 kis-tooltip" style={{ color: "var(--foreground)" }}
                        data-tip={generating ? undefined : s.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "").replace(/^(Flashcards|Cloze|Vocabulary test|Term quiz|Quiz)\s*(from|of)\s*/i, "")}>
                        {generating ? generatingLabel : s.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "").replace(/^(Flashcards|Cloze|Vocabulary test|Term quiz|Quiz)\s*(from|of)\s*/i, "")}
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
                        {generating ? modeLabel : failed ? t("exerciseSets.failed") : t("exerciseSets.cardsCount", { count: s.card_count })}
                        {!generating && s.mode === "glossary" && t("exerciseSets.fromGlossarySuffix")}
                        {!generating && ` · ${new Date(s.created_at).toLocaleDateString(dateLocale, { day: "numeric", month: "short", timeZone: "Europe/Berlin" })}`}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {!generating && onDownload && (
                          <button type="button" onClick={(e) => { e.stopPropagation(); onDownload(s); }}
                            className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                            style={{ backgroundColor: "var(--surface-dim)" }}
                            title={t("common.downloadAsText")}>
                            <DownloadSimple size={12} />
                          </button>
                        )}
                        {!generating && <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                          className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                          style={{ backgroundColor: "var(--surface-dim)" }}
                          title={t("common.delete")}>
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
