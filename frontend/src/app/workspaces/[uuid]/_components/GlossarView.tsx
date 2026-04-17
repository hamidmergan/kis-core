import { useEffect, useRef, useState } from "react";
import { Book, DotsThreeVertical, FilePdf, Files, Plus, Trash } from "@phosphor-icons/react";
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
  onOpenSource?: (page: number, highlightText?: string) => void;
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
          <div className="relative flex items-center justify-center gap-1.5 px-1">
            <button
              type="button"
              onClick={onGenerate}
              disabled={loading || noSources}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
              style={{ color: "var(--accent)", backgroundColor: "#fff", border: "1.5px solid var(--accent)" }}
            >
              {loading ? <Spinner size="xs" color="current" /> : <Plus size={12} weight="bold" />}
              {loading ? "Begriffe werden extrahiert…" : "Begriffe extrahieren"}
            </button>
            <HelpTooltip text="Extrahiert 10–20 Fachbegriffe aus den ausgewählten Quellen. Maximal 150 Einträge." />
            {entries.length > 0 && (
              <div className="absolute right-0 flex items-center gap-1.5">
                <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>{entries.length}/150</span>
                <GlossarMenu onDeleteAll={onDeleteAll} />
              </div>
            )}
          </div>

          {entries.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
              <Book size={32} weight="light" />
              <span className="text-xs text-center">Noch kein Glossar generiert. Klicke oben auf „Begriffe extrahieren", um Fachbegriffe aus deinen Quellen zu extrahieren.</span>
            </div>
          )}

          {entries.map((entry) => (
            <div
              key={entry.id}
              className="rounded-xl p-4 flex flex-col gap-2 relative group select-text"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", userSelect: "text" }}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-sm font-bold" style={{ color: "var(--text)" }}>{entry.term_de}</span>
                  {showTranslation && <span className="text-sm font-medium ml-2" style={{ color: "var(--accent)" }}>{entry.term_en}</span>}
                </div>
                {entry.page_number && (() => {
                  const ChipIcon = entry.filename ? _getChipIcon(entry.filename) : FilePdf;
                  return (
                  <span role="button" tabIndex={0} onClick={() => onOpenSource?.(entry.page_number!, entry.term_de)}
                    onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
                    className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 hover:opacity-80 transition-opacity cursor-pointer"
                    style={{ backgroundColor: "rgba(var(--accent-rgb),0.12)", color: "var(--accent)" }}>
                    <ChipIcon size={8} weight="bold" /> {entry.filename ? _chunkLabel(entry.filename, entry.page_number!) : `S. ${entry.page_number}`}
                  </span>
                  );
                })()}
              </div>
              {showTranslation && (entry.example_sentence) && (
                <div>
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
              <div className="flex justify-end mt-1">
                <button type="button" onClick={() => onDelete?.(entry.id)}
                  className="w-5 h-5 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                  style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
                  <Trash size={10} />
                </button>
              </div>
            </div>
          ))}

        </div>
      </div>
    </div>
  );
}

