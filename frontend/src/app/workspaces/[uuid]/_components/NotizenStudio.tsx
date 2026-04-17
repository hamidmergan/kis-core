import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CaretDown, CaretUp, NotePencil, Plus, Trash } from "@phosphor-icons/react";
import type { Source, StudentStats } from "../_types";
import { _chunkLabel, _getChipIcon, _isMediaFile, _sourceChipKey } from "../_utils";
import { SubviewHeader } from "./SubviewHeader";

export interface Note { id: number; content: string; created_at: string | null }

export function NotizenStudio({
  notes, onAdd, onDelete, onBack, sources, activeSourceIds, onPillClick, stats, breadcrumbs,
}: {
  notes: Note[]; onAdd: (content: string) => void; onDelete: (id: number) => void; onBack?: () => void;
  sources?: Source[]; activeSourceIds?: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [draft, setDraft] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [sourcesExpanded, setSourcesExpanded] = useState<Set<number>>(new Set());

  // Extract unique sources from note content (for chip numbering + accordion)
  function extractNoteSources(content: string): { qnum: number; uuid: string; filename: string }[] {
    const pattern = /\[(?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*[|\u2758]\s*[^\]]+)?\s*\]/g;
    const seen = new Map<string, { qnum: number; uuid: string; filename: string }>();
    let qCounter = 0;
    let m: RegExpExecArray | null;
    while ((m = pattern.exec(content)) !== null) {
      const qIdx = m[1] ? parseInt(m[1]) - 1 : 0;
      const embeddedUuid = m[2] || null;
      const uuid = embeddedUuid ?? activeSourceIds?.[qIdx] ?? activeSourceIds?.[0] ?? "";
      if (!uuid || seen.has(uuid)) continue;
      const filename = sources?.find(s => s.uuid === uuid)?.filename ?? uuid;
      qCounter++;
      seen.set(uuid, { qnum: qCounter, uuid, filename });
    }
    return Array.from(seen.values());
  }
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [draft]);

  function makeNoteCitationRenderer(noteSources: { qnum: number; uuid: string }[]) {
    let chipKey = 0;
    function parseNoteCitations(text: string): React.ReactNode[] {
      // Matches [1, S. 2 | kw], [Q1:uuid, S. 2 | kw], [S. 2], [1, 05:32 | kw]
      const pattern = /\[(?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))(?:\s*[|\u2758]\s*([^\]]+))?\s*\]/g;
      const nodes: React.ReactNode[] = [];
      let last = 0;
      let m: RegExpExecArray | null;
      while ((m = pattern.exec(text)) !== null) {
        if (m.index > last) nodes.push(text.slice(last, m.index));
        const qIdx = m[1] ? parseInt(m[1]) - 1 : 0;
        const embeddedUuid = m[2] || null;
        const pageNum = m[3] ? parseInt(m[3]) : 0;
        const timestamp = m[4] || null;
        const keyword = m[5]?.trim() || undefined;
        const isMedia = !!timestamp;

        const sourceUuid = embeddedUuid
          ?? activeSourceIds?.[qIdx]
          ?? (isMedia
            ? sources?.find(s => _isMediaFile(s.filename))?.uuid
            : sources?.find(s => !_isMediaFile(s.filename))?.uuid)
          ?? activeSourceIds?.[0]
          ?? "";
        const filename = sources?.find(s => s.uuid === sourceUuid)?.filename ?? sourceUuid;
        const displayQNum = noteSources.find(s => s.uuid === sourceUuid)?.qnum ?? null;

        let startTime: number | undefined;
        if (timestamp) {
          const parts = timestamp.split(":").map(Number);
          startTime = parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1];
        }

        const ChipIcon = _getChipIcon(filename);
        const label = timestamp ?? _chunkLabel(filename, pageNum);
        const ck = `n${chipKey++}`;
        nodes.push(
          <span
            key={ck}
            role="button"
            tabIndex={0}
            onClick={(e) => { e.stopPropagation(); onPillClick?.(sourceUuid, pageNum, filename, keyword, startTime); }}
            onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
            className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity align-middle mx-0.5 cursor-pointer"
            style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
            title={`${filename}, ${label}`}
          >
            <ChipIcon size={8} weight="bold" />
            {displayQNum ? `[${displayQNum}] ` : ""}{label}
          </span>
        );
        last = pattern.lastIndex;
      }
      if (last < text.length) nodes.push(text.slice(last));
      return nodes;
    }
    function withNoteCitations(children: React.ReactNode): React.ReactNode {
      const arr: React.ReactNode[] = Array.isArray(children) ? children : [children];
      return arr.flatMap((child) =>
        typeof child === "string" ? parseNoteCitations(child) : [child]
      );
    }
    return { withNoteCitations };
  }

  return (
    <div className="flex flex-col h-full">
      {onBack && <SubviewHeader title="Notizen" onBack={onBack} breadcrumbs={breadcrumbs} />}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-3" style={{ maxWidth: 560 }}>
          {/* New note input */}
          <div
            className="flex gap-2 items-center rounded-xl p-2"
            style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}
          >
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => { if (e.target.value.length <= 2000) setDraft(e.target.value); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && draft.trim()) { e.preventDefault(); onAdd(draft.trim()); setDraft(""); }
              }}
              placeholder="Neue Notiz…"
              maxLength={2000}
              rows={1}
              className="flex-1 text-sm resize-none focus:outline-none bg-transparent"
              style={{ color: "var(--text)", maxHeight: 160, overflowY: "auto" }}
            />
            {draft.length > 1800 && (
              <span className="text-[10px] flex-shrink-0" style={{ color: draft.length >= 2000 ? "#ef4444" : "var(--muted)" }}>
                {draft.length}/2000
              </span>
            )}
            <button
              type="button"
              onClick={() => { if (draft.trim()) { onAdd(draft.trim()); setDraft(""); } }}
              disabled={!draft.trim()}
              className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-white disabled:opacity-40 transition-opacity hover:opacity-85"
              style={{ backgroundColor: "var(--kb)" }}
              title="Notiz speichern"
            >
              <Plus size={14} weight="bold" />
            </button>
          </div>

          {/* Notes grid */}
          {notes.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
              <NotePencil size={32} weight="light" />
              <span className="text-xs text-center">Noch keine Notizen. Erstelle eine oben oder speichere eine KI-Antwort als Notiz.</span>
            </div>
          )}
          <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
            {notes.map((note) => {
              const isExpanded = expandedId === note.id;
              const noteSources = extractNoteSources(note.content);
              const { withNoteCitations } = makeNoteCitationRenderer(noteSources);
              const sourcesOpen = sourcesExpanded.has(note.id);
              return (
                <div
                  key={note.id}
                  className="group relative rounded-xl p-3 cursor-pointer hover:opacity-80 transition-opacity flex flex-col"
                  style={{
                    backgroundColor: "var(--background)",
                    boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)",
                    minHeight: 90,
                    ...(isExpanded ? { gridColumn: "1 / -1" } : {}),
                  }}
                  onClick={() => setExpandedId(isExpanded ? null : note.id)}
                >
                  <div
                    className={`text-sm pr-6 ki-note-content overflow-hidden flex-1 ${isExpanded ? "" : "max-h-[4.5em]"}`}
                    style={{ color: "var(--text)", ...(isExpanded ? {} : { WebkitMaskImage: "linear-gradient(to bottom, black 60%, transparent 100%)" }) }}
                  >
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <p className="mb-2 last:mb-0">{withNoteCitations(children)}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                        li: ({ children }) => <li className="leading-relaxed">{withNoteCitations(children)}</li>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        h1: ({ children }) => <p className="font-semibold mb-1">{withNoteCitations(children)}</p>,
                        h2: ({ children }) => <p className="font-semibold mb-1">{withNoteCitations(children)}</p>,
                        h3: ({ children }) => <p className="font-medium mb-1">{withNoteCitations(children)}</p>,
                        table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-xs border-collapse">{children}</table></div>,
                        th: ({ children }) => <th className="text-left px-2 py-1 font-medium border-b" style={{ borderColor: "var(--border)" }}>{children}</th>,
                        td: ({ children }) => <td className="px-2 py-1 border-b" style={{ borderColor: "var(--border)" }}>{withNoteCitations(children)}</td>,
                        hr: () => <hr className="my-3" style={{ borderColor: "var(--border)" }} />,
                      }}
                    >
                      {note.content.replace(/\[([^\]]*\|[^\]]*)\]/g, (m) => m.replace(/\|/g, "\u2758"))}
                    </ReactMarkdown>
                  </div>
                  {noteSources.length > 0 && (
                    <div className="mt-1" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => setSourcesExpanded((prev) => {
                          const next = new Set(prev);
                          next.has(note.id) ? next.delete(note.id) : next.add(note.id);
                          return next;
                        })}
                        className="flex items-center gap-1 text-[10px] hover:opacity-80 transition-opacity"
                        style={{ color: "var(--muted)" }}
                      >
                        {sourcesOpen ? <CaretUp size={10} /> : <CaretDown size={10} />}
                        {noteSources.length} {noteSources.length === 1 ? "Quelle" : "Quellen"}
                      </button>
                      {sourcesOpen && (
                        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 ml-3.5">
                          {noteSources.map((s) => {
                            const ChipIcon = _getChipIcon(s.filename);
                            return (
                              <span
                                key={s.qnum}
                                role="button"
                                tabIndex={0}
                                onClick={(e) => { e.stopPropagation(); onPillClick?.(s.uuid, 0, s.filename); }}
                                onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
                                className="inline-flex items-center gap-1 text-[10px] cursor-pointer hover:opacity-70 transition-opacity"
                                style={{ color: "var(--muted)" }}
                                title={s.filename}
                              >
                                <ChipIcon size={10} weight="bold" />
                                <span style={{ color: "var(--kb)" }}>[{s.qnum}]</span>
                                <span className="max-w-[160px] truncate">{s.filename}</span>
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                  <div className="flex items-center justify-between mt-auto pt-1">
                    <span className="text-[10px] font-medium" style={{ color: "var(--muted)" }}>
                      {note.created_at ? new Date(note.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                    </span>
                    <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(note.id); }}
                      className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                      style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
                      <Trash size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
