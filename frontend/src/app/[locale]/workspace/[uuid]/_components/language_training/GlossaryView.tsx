import { useEffect, useMemo, useRef, useState } from "react";
import { Book, CaretDown, CaretUp, ClockCounterClockwise, DotsThreeVertical, FilePdf, TextAa, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { GlossaryEntry, StudentStats } from "../../_types";
import { _chunkLabel, _getChipIcon } from "../../_utils";
import { SubviewHeader, type BreadcrumbItem } from "../layout/SubviewHeader";

export function GlossaryMenu({ onDeleteAll }: { onDeleteAll?: () => void }) {
  const t = useTranslations("workspace.detail.languageTraining.glossary");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(!open)}
        className="w-5 h-5 flex items-center justify-center rounded-full btn-icon"
        style={{ backgroundColor: "var(--surface-dim)" }}>
        <DotsThreeVertical size={12} weight="bold" />
      </button>
      {open && (
        <div className="absolute right-0 top-6 z-50 rounded-xl py-1"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", minWidth: 180, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}>
          <button type="button"
            onClick={() => { setOpen(false); onDeleteAll?.(); }}
            className="w-full text-left px-4 py-2.5 text-sm hover:bg-[var(--surface-dim)] transition-colors"
            style={{ color: "var(--error-strong)" }}>
            {t("deleteAll")}
          </button>
        </div>
      )}
    </div>
  );
}

export function GlossaryView({
  entries, extracting, onBack, onOpenSource, onDelete, onDeleteAll, stats, breadcrumbs, showTranslation, feedback, onDismissFeedback,
}: {
  entries: GlossaryEntry[]; extracting?: boolean;
  onBack?: () => void;
  onOpenSource?: (filename: string | undefined, page: number, highlightText?: string, startTime?: number | null) => void;
  onDelete?: (id: number) => void;
  onDeleteAll?: () => void;
  stats?: StudentStats | null;
  breadcrumbs?: BreadcrumbItem[];
  showTranslation?: boolean;
  feedback?: { kind: "success" | "info" | "error"; message: string } | null;
  onDismissFeedback?: () => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const tChip = useTranslations("sourceChip");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [sortMode, setSortMode] = useState<"recent" | "alpha">("recent");
  const sortedEntries = useMemo(() => {
    if (sortMode === "alpha") {
      return [...entries].sort((a, b) => a.term_de.localeCompare(b.term_de, "de", { sensitivity: "base" }));
    }
    return [...entries].sort((a, b) => b.id - a.id);
  }, [entries, sortMode]);
  return (
    <div className="flex flex-col h-full">
      {onBack && <SubviewHeader title={t("glossary.title")} toolKey="Glossary" onBack={onBack} breadcrumbs={breadcrumbs} category="language_training" />}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {entries.length > 0 && (
          <div className="w-full px-1 flex items-center justify-end">
            <GlossaryMenu onDeleteAll={onDeleteAll} />
          </div>
        )}

        <div className="mx-auto w-full px-1 pb-3 flex flex-col gap-3" style={{ maxWidth: 560 }}>
          {extracting && (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs font-medium"
              style={{ backgroundColor: "rgba(var(--kb-rgb),0.06)", color: "var(--kb)" }}>
              <Spinner size="xs" color="current" />
              {t("glossary.extractingMarkup")}
            </div>
          )}
          {!extracting && feedback && (
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-xl text-xs font-medium"
              style={{
                backgroundColor: feedback.kind === "success" ? "rgba(22,163,74,0.08)" : feedback.kind === "error" ? "rgba(185,28,28,0.08)" : "rgba(100,116,139,0.1)",
                color: feedback.kind === "success" ? "var(--success-strong)" : feedback.kind === "error" ? "var(--error-strong)" : "var(--foreground-soft)",
              }}>
              <span className="flex-1">{feedback.message}</span>
              {onDismissFeedback && (
                <button type="button" onClick={onDismissFeedback} className="opacity-60 hover:opacity-100 text-xs leading-none" aria-label={t("common.close")}>×</button>
              )}
            </div>
          )}
          {entries.length === 0 && (
            <EmptyState
              size="sm"
              icon={<Book size={32} weight="bold" />}
              text={t("glossary.emptyTitle")}
            />
          )}
        </div>

        {entries.length > 1 && (
          <div className="w-full flex justify-end gap-1 px-1" role="group" aria-label={t("glossary.sortAriaLabel")}>
            {(["recent", "alpha"] as const).map((mode) => {
              const active = sortMode === mode;
              const Icon = mode === "recent" ? ClockCounterClockwise : TextAa;
              return (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setSortMode(mode)}
                  aria-pressed={active}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-colors"
                  style={{
                    backgroundColor: active ? "var(--kb)" : "transparent",
                    color: active ? "#fff" : "var(--muted)",
                  }}
                >
                  <Icon size={12} weight="bold" />
                  {t(mode === "recent" ? "glossary.sortRecent" : "glossary.sortAlpha")}
                </button>
              );
            })}
          </div>
        )}

        {entries.length > 0 && (
          <div className="w-full px-1 pb-3">
            <div
              className="rounded-xl overflow-hidden"
              style={{
                backgroundColor: "var(--background)",
                boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)",
              }}
            >
              {sortedEntries.map((entry, idx) => {
                const isExpanded = expandedId === entry.id;
                const isLast = idx === sortedEntries.length - 1;
                const ChipIcon = entry.filename ? _getChipIcon(entry.filename) : FilePdf;
                return (
                  <div key={entry.id} style={{ borderBottom: isLast && !isExpanded ? "none" : "1px solid var(--border)" }}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setExpandedId(isExpanded ? null : entry.id); } }}
                      className="group flex items-center gap-3 px-3 cursor-pointer hover:bg-[var(--surface-dim)] transition-colors"
                      style={{ minHeight: 48, color: "var(--foreground)" }}
                    >
                      <span className="flex-1 text-sm truncate">
                        <span className="font-bold">{entry.term_de}</span>
                        {showTranslation && entry.term_en && (
                          <span className="font-medium ml-2" style={{ color: "var(--kb)" }}>{entry.term_en}</span>
                        )}
                      </span>
                      {entry.page_number && (
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={(e) => { e.stopPropagation(); onOpenSource?.(entry.filename, entry.page_number!, entry.term_de, entry.start_time); }}
                          onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); e.currentTarget.click(); } }}
                          className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 chip-cite cursor-pointer"
                          style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
                        >
                          <ChipIcon size={8} weight="bold" /> {entry.filename ? _chunkLabel(entry.filename, entry.page_number!, entry.start_time, (key, vals) => tChip(key, vals)) : t("glossary.pageShort", { page: entry.page_number })}
                        </span>
                      )}
                      {isExpanded
                        ? <CaretUp size={14} weight="bold" className="group-hover:text-[var(--kb)] transition-colors" />
                        : <CaretDown size={14} weight="bold" className="group-hover:text-[var(--kb)] transition-colors" />}
                    </div>

                    {isExpanded && (
                      <div className="px-3 pb-3 pt-1" onClick={(e) => e.stopPropagation()}>
                        {showTranslation && entry.example_sentence && (
                          <div className="mb-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--kb)" }}>{t("glossary.context")}</span>
                            <p className="text-sm italic leading-relaxed mt-0.5" >
                              „{entry.example_sentence}"
                            </p>
                          </div>
                        )}
                        <div>
                          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--kb)" }}>{t("glossary.explanation")}</span>
                          <p className="text-sm leading-relaxed mt-0.5" style={{ color: "var(--foreground)", opacity: 0.8 }}>
                            {entry.definition}
                          </p>
                        </div>
                        <div className="flex justify-end mt-3">
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onDelete?.(entry.id); }}
                            className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                            style={{ backgroundColor: "var(--surface-dim)" }}
                          >
                            <Trash size={12} />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
