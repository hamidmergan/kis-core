import { useEffect, useRef, useState } from "react";
import { Book, CaretDown, CaretUp, DotsThreeVertical, FilePdf, Files, Sparkle, Trash } from "@phosphor-icons/react";
import HelpTooltip from "@/components/ui/HelpTooltip";
import Spinner from "@/components/ui/Spinner";
import type { GlossaryEntry, StudentStats } from "../_types";
import { _chunkLabel, _getChipIcon } from "../_utils";
import { SubviewHeader } from "./SubviewHeader";

export function GlossarMenu({ onDeleteAll }: { onDeleteAll?: () => void }) {
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
        className="w-5 h-5 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
        style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
        <DotsThreeVertical size={12} weight="bold" />
      </button>
      {open && (
        <div className="absolute right-0 top-6 z-50 rounded-lg py-1"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", minWidth: 160, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}>
          <button type="button"
            onClick={() => { setOpen(false); onDeleteAll?.(); }}
            className="w-full text-left px-3 py-1.5 text-[11px] hover:opacity-70 transition-opacity"
            style={{ color: "#B91C1C" }}>
            Alle Begriffe löschen
          </button>
        </div>
      )}
    </div>
  );
}

export function GlossarView({
  entries, loading, extracting, onGenerate, onBack, onOpenSource, onDelete, onDeleteAll, sourceCount = 0, stats, breadcrumbs, showTranslation, feedback, onDismissFeedback,
}: {
  entries: GlossaryEntry[]; loading: boolean; extracting?: boolean;
  onGenerate: () => void; onBack?: () => void;
  onOpenSource?: (page: number, highlightText?: string, startTime?: number | null) => void;
  onDelete?: (id: number) => void;
  onDeleteAll?: () => void;
  sourceCount?: number;
  stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
  showTranslation?: boolean;
  feedback?: { kind: "success" | "info" | "error"; message: string } | null;
  onDismissFeedback?: () => void;
}) {
  const noSources = sourceCount === 0;
  const [expandedId, setExpandedId] = useState<number | null>(null);
  return (
    <div className="flex flex-col h-full">
      {onBack && <SubviewHeader title="Glossar" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        <div className="rounded-xl px-3 py-2 text-xs font-medium flex items-center gap-2"
          style={{
            color: noSources ? "#B91C1C" : sourceCount > 5 ? "#c4820e" : "var(--kb)",
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
        <div className="relative w-full px-1 flex items-center justify-center gap-1.5">
          <button
            type="button"
            onClick={onGenerate}
            disabled={loading || noSources}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
            style={{ color: "var(--accent)", backgroundColor: "#fff", border: "1.5px solid var(--accent)" }}
          >
            {loading ? <Spinner size="xs" color="current" /> : <Sparkle size={12} weight="bold" />}
            {loading ? "Begriffe werden extrahiert…" : `Begriffe extrahieren (${entries.length}/150)`}
          </button>
          <HelpTooltip text="Extrahiert Fachbegriffe aus den ausgewählten Quellen." />
          {entries.length > 0 && (
            <div className="absolute right-1 flex items-center">
              <GlossarMenu onDeleteAll={onDeleteAll} />
            </div>
          )}
        </div>

        <div className="mx-auto w-full px-1 pb-3 flex flex-col gap-3" style={{ maxWidth: 560 }}>
          {extracting && (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs font-medium"
              style={{ backgroundColor: "rgba(var(--accent-rgb),0.06)", color: "var(--accent)" }}>
              <Spinner size="xs" color="current" />
              Begriffe werden aus Markierung extrahiert…
            </div>
          )}
          {!extracting && feedback && (
            <div className="flex items-start gap-2 px-3 py-2.5 rounded-xl text-xs font-medium"
              style={{
                backgroundColor: feedback.kind === "success" ? "rgba(22,163,74,0.08)" : feedback.kind === "error" ? "rgba(185,28,28,0.08)" : "rgba(100,116,139,0.1)",
                color: feedback.kind === "success" ? "#166534" : feedback.kind === "error" ? "#B91C1C" : "#334155",
              }}>
              <span className="flex-1">{feedback.message}</span>
              {onDismissFeedback && (
                <button type="button" onClick={onDismissFeedback} className="opacity-60 hover:opacity-100 text-xs leading-none" aria-label="Schließen">×</button>
              )}
            </div>
          )}
          {entries.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
              <Book size={32} weight="light" />
              <span className="text-xs text-center">Noch kein Glossar generiert. Klicke oben auf „Begriffe extrahieren", um Fachbegriffe aus deinen Quellen zu extrahieren.</span>
            </div>
          )}
        </div>

        {entries.length > 0 && (
          <div className="w-full px-1 pb-3">
            <div
              className="rounded-xl overflow-hidden"
              style={{
                backgroundColor: "var(--background)",
                boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)",
              }}
            >
              {entries.map((entry, idx) => {
                const isExpanded = expandedId === entry.id;
                const isLast = idx === entries.length - 1;
                const ChipIcon = entry.filename ? _getChipIcon(entry.filename) : FilePdf;
                return (
                  <div key={entry.id} style={{ borderBottom: isLast && !isExpanded ? "none" : "1px solid var(--border)" }}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setExpandedId(isExpanded ? null : entry.id); } }}
                      className="flex items-center gap-3 px-3 cursor-pointer hover:opacity-80 transition-opacity"
                      style={{ minHeight: 48, color: "var(--text)" }}
                    >
                      <span className="flex-1 text-sm truncate">
                        <span className="font-bold">{entry.term_de}</span>
                        {showTranslation && entry.term_en && (
                          <span className="font-medium ml-2" style={{ color: "var(--accent)" }}>{entry.term_en}</span>
                        )}
                      </span>
                      {entry.page_number && (
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={(e) => { e.stopPropagation(); onOpenSource?.(entry.page_number!, entry.term_de, entry.start_time); }}
                          onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); e.currentTarget.click(); } }}
                          className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 hover:opacity-80 transition-opacity cursor-pointer"
                          style={{ backgroundColor: "rgba(var(--accent-rgb),0.12)", color: "var(--accent)" }}
                        >
                          <ChipIcon size={8} weight="bold" /> {entry.filename ? _chunkLabel(entry.filename, entry.page_number!, entry.start_time) : `S. ${entry.page_number}`}
                        </span>
                      )}
                      {isExpanded
                        ? <CaretUp size={14} style={{ color: "var(--muted)" }} />
                        : <CaretDown size={14} style={{ color: "var(--muted)" }} />}
                    </div>

                    {isExpanded && (
                      <div className="px-3 pb-3 pt-1" onClick={(e) => e.stopPropagation()}>
                        {showTranslation && entry.example_sentence && (
                          <div className="mb-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--accent)" }}>Kontext</span>
                            <p className="text-sm italic leading-relaxed mt-0.5" style={{ color: "var(--muted)" }}>
                              „{entry.example_sentence}"
                            </p>
                          </div>
                        )}
                        <div>
                          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--accent)" }}>Erklärung (B1)</span>
                          <p className="text-sm leading-relaxed mt-0.5" style={{ color: "var(--text)", opacity: 0.8 }}>
                            {entry.definition}
                          </p>
                        </div>
                        <div className="flex justify-end mt-3">
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onDelete?.(entry.id); }}
                            className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
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

