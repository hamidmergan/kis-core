import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CaretDown, CaretUp, NotePencil, Plus, Trash } from "@phosphor-icons/react";
import type { Source, StudentStats } from "../_types";
import { _chunkLabel, _getChipIcon, _isMediaFile, _sourceChipKey } from "../_utils";
import { SubviewHeader } from "./SubviewHeader";

export interface Note { id: number; title?: string | null; content: string; created_at: string | null }

function _notePreview(content: string, max = 60): string {
  const stripped = content
    .replace(/\[[^\]]*\]/g, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#+\s+/gm, "")
    .replace(/^\s*[->*+]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!stripped) return "(leere Notiz)";
  return stripped.length > max ? stripped.slice(0, max).trimEnd() + "…" : stripped;
}

export function NotizenStudio({
  notes, onAdd, onDelete, onUpdateTitle, onBack, sources, activeSourceIds, onPillClick, stats, breadcrumbs,
}: {
  notes: Note[]; onAdd: (content: string) => void; onDelete: (id: number) => void;
  onUpdateTitle?: (id: number, title: string | null) => void;
  onBack?: () => void;
  sources?: Source[]; activeSourceIds?: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [draft, setDraft] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const skipTitleCommitRef = useRef(false);

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
        <div className="w-full px-4 pt-4 pb-6 flex flex-col gap-3">
          {/* New note input */}
          <div
            className="mx-auto w-full flex gap-2 items-center rounded-xl p-2"
            style={{ maxWidth: 640, backgroundColor: "var(--background)", border: "1px solid var(--border)" }}
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

          {/* Empty state */}
          {notes.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
              <NotePencil size={32} weight="light" />
              <span className="text-xs text-center">Noch keine Notizen. Erstelle eine oben oder speichere eine KI-Antwort als Notiz.</span>
            </div>
          )}

          {/* Notes table (accordion rows) */}
          {notes.length > 0 && (
            <div
              className="rounded-xl overflow-hidden"
              style={{
                backgroundColor: "var(--background)",
                boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)",
              }}
            >
              {notes.map((note, idx) => {
                const isExpanded = expandedId === note.id;
                const noteSources = extractNoteSources(note.content);
                const { withNoteCitations } = makeNoteCitationRenderer(noteSources);
                const isLast = idx === notes.length - 1;
                const hasCustomTitle = !!(note.title && note.title.trim());
                const rowLabel = hasCustomTitle ? note.title!.trim() : _notePreview(note.content);
                const isEditingTitle = editingTitleId === note.id;

                function commitTitle() {
                  if (skipTitleCommitRef.current) {
                    skipTitleCommitRef.current = false;
                    setEditingTitleId(null);
                    return;
                  }
                  if (!isEditingTitle) return;
                  const clean = titleDraft.trim();
                  const next = clean === "" ? null : clean;
                  if ((note.title ?? null) !== next) onUpdateTitle?.(note.id, next);
                  setEditingTitleId(null);
                }

                return (
                  <div key={note.id} style={{ borderBottom: isLast && !isExpanded ? "none" : "1px solid var(--border)" }}>
                    {/* Row */}
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => setExpandedId(isExpanded ? null : note.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setExpandedId(isExpanded ? null : note.id); } }}
                      className="flex items-center gap-3 px-3 cursor-pointer hover:opacity-80 transition-opacity"
                      style={{ minHeight: 48, color: "var(--text)" }}
                    >
                      <span
                        className="flex-1 text-sm truncate"
                        style={hasCustomTitle ? { fontWeight: 500 } : { color: "var(--muted)", fontStyle: "italic" }}
                      >
                        {rowLabel}
                      </span>
                      <span className="flex-shrink-0 text-[10px]" style={{ color: "var(--muted)" }}>
                        {note.created_at ? new Date(note.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", timeZone: "Europe/Berlin" }) : ""}
                      </span>
                      {isExpanded
                        ? <CaretUp size={14} style={{ color: "var(--muted)" }} />
                        : <CaretDown size={14} style={{ color: "var(--muted)" }} />}
                    </div>

                    {/* Accordion */}
                    {isExpanded && (
                      <div
                        className="px-3 pb-3 pt-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {/* Title — click to reveal edit mode */}
                        {onUpdateTitle && (
                          isEditingTitle ? (
                            <input
                              autoFocus
                              type="text"
                              value={titleDraft}
                              onChange={(e) => setTitleDraft(e.target.value.slice(0, 200))}
                              onBlur={commitTitle}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { e.preventDefault(); (e.currentTarget as HTMLInputElement).blur(); }
                                else if (e.key === "Escape") { e.preventDefault(); skipTitleCommitRef.current = true; (e.currentTarget as HTMLInputElement).blur(); }
                              }}
                              placeholder="Titel vergeben…"
                              maxLength={200}
                              className="w-full text-sm font-medium mb-2 px-2 py-1 rounded-md focus:outline-none"
                              style={{ backgroundColor: "var(--surface-dim)", color: "var(--text)", border: "1px solid var(--border)" }}
                            />
                          ) : (
                            <button
                              type="button"
                              onClick={() => { setTitleDraft(note.title ?? ""); setEditingTitleId(note.id); }}
                              className="w-full text-left text-sm font-medium mb-2 px-2 py-1 rounded-md hover:bg-[var(--surface-dim)] transition-colors truncate"
                              style={hasCustomTitle ? { color: "var(--text)" } : { color: "var(--muted)", fontStyle: "italic", fontWeight: 400 }}
                              title={hasCustomTitle ? "Titel ändern" : "Titel vergeben"}
                            >
                              {hasCustomTitle ? note.title : "Titel vergeben…"}
                            </button>
                          )
                        )}

                        <div className="text-sm ki-note-content" style={{ color: "var(--text)" }}>
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
                          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
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

                        <div className="flex items-center justify-between mt-3">
                          <span className="text-[10px]" style={{ color: "var(--muted)" }}>
                            {note.created_at ? new Date(note.created_at).toLocaleString("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onDelete(note.id); }}
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
          )}
        </div>
      </div>
    </div>
  );
}
