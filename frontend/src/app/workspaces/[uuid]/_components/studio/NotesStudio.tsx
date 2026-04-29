import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CaretDown, CaretUp, NotePencil, PencilSimple, Plus, Trash, X } from "@phosphor-icons/react";
import type { ChatMessage, Source, SourceQmap, SourceRef, StudentStats } from "../../_types";
import { _getChipIcon } from "../../_utils";
import { withCitations, type CitationChipClickHandler } from "../chat/_citations";
import { SubviewHeader, type BreadcrumbItem } from "../layout/SubviewHeader";
import Spinner from "@/components/ui/Spinner";

export interface Note {
  id: number;
  title?: string | null;
  content: string;
  source_uuids?: string[] | null;
  source_pages?: SourceRef[] | null;
  popup_selection?: { uuid: string; page: number; text: string } | null;
  created_at: string | null;
}

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

export function NotesStudio({
  notes, onAdd, onDelete, onUpdateTitle, onBack, sources, activeSourceIds, onPillClick, stats, breadcrumbs, pendingTitleIds,
}: {
  notes: Note[]; onAdd: (content: string) => void; onDelete: (id: number) => void;
  onUpdateTitle?: (id: number, title: string | null) => void;
  onBack?: () => void;
  sources?: Source[]; activeSourceIds?: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
  stats?: StudentStats | null;
  breadcrumbs?: BreadcrumbItem[];
  pendingTitleIds?: Set<number>;
}) {
  const [draft, setDraft] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const skipTitleCommitRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const getFilename = (uuid: string) => sources?.find(s => s.uuid === uuid)?.filename ?? uuid;
  const onChipClick: CitationChipClickHandler = (uuid, page, filename, sourceText, startTime, isExact) =>
    onPillClick?.(uuid, page, filename, sourceText, startTime, isExact);

  // Builds a chat-message-shaped object so the chat citation renderer can be reused 1:1.
  // qmap entries also feed the source list at the bottom of each expanded note.
  function noteAsMessage(note: Note): { msg: ChatMessage; qmap: SourceQmap[] } {
    const qmap: SourceQmap[] = (note.source_uuids ?? []).map((uuid, i) => ({
      qnum: i + 1,
      uuid,
      filename: getFilename(uuid),
    }));
    const msg: ChatMessage = {
      role: "assistant",
      content: note.content,
      source_qmap: qmap,
      source_pages: note.source_pages ?? undefined,
      popup_selection: note.popup_selection ?? undefined,
    };
    return { msg, qmap };
  }

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [draft]);

  return (
    <div className="flex flex-col h-full">
      {onBack && <SubviewHeader title="Notizen" toolKey="Notes" onBack={onBack} breadcrumbs={breadcrumbs} />}
      <div className="flex-1 overflow-y-auto">
        <div className="w-full px-4 pt-4 pb-6 flex flex-col gap-3">
          {/* New note input */}
          <div
            className="mx-auto w-full flex gap-2 items-center rounded-xl p-2 border-2 border-[var(--border)] hover:border-[var(--accent)] focus-within:border-[var(--accent)] transition-colors"
            style={{ maxWidth: 640, backgroundColor: "var(--background)" }}
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
            {draft && (
              <button
                type="button"
                onClick={() => { setDraft(""); textareaRef.current?.focus(); }}
                className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full btn-icon"
                title="Eingabe löschen"
              >
                <X size={14} weight="bold" />
              </button>
            )}
            <button
              type="button"
              onClick={() => { if (draft.trim()) { onAdd(draft.trim()); setDraft(""); } }}
              disabled={!draft.trim()}
              className="btn-fill-accent flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg disabled:opacity-40 transition-colors"
              title="Notiz speichern"
            >
              <Plus size={14} weight="bold" />
            </button>
          </div>

          {/* Empty state */}
          {notes.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-2 py-8" >
              <NotePencil size={32} weight="light" />
              <span className="text-xs text-center">Noch keine Notes. Erstelle eine oben oder speichere eine KI-Antwort als Notiz.</span>
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
                const { msg, qmap } = noteAsMessage(note);
                const wrapCitations = (children: React.ReactNode) =>
                  withCitations(children, msg, activeSourceIds ?? [], getFilename, onChipClick);
                const isLast = idx === notes.length - 1;
                const hasCustomTitle = !!(note.title && note.title.trim());
                const isTitlePending = !hasCustomTitle && !!pendingTitleIds?.has(note.id);
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
                      className="row-expandable flex items-center gap-3 px-3 cursor-pointer hover:bg-[var(--surface-dim)] transition-colors"
                      style={{ minHeight: 48, color: "var(--text)" }}
                    >
                      <span
                        className="flex-1 text-sm truncate flex items-center gap-2"
                        style={hasCustomTitle ? { fontWeight: 500 } : { fontStyle: "italic" }}
                      >
                        {isTitlePending && <Spinner size="xs" color="current" />}
                        <span className="truncate">{rowLabel}</span>
                      </span>
                      <span className="flex-shrink-0 text-[10px] text-[var(--muted)]">
                        {note.created_at ? new Date(note.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", timeZone: "Europe/Berlin" }) : ""}
                      </span>
                      <span className="row-caret flex-shrink-0 transition-colors">
                        {isExpanded ? <CaretUp size={14} /> : <CaretDown size={14} />}
                      </span>
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
                              disabled={isTitlePending}
                              onClick={() => { setTitleDraft(note.title ?? ""); setEditingTitleId(note.id); }}
                              className="group w-full text-left text-sm font-medium mb-2 px-2 py-1 rounded-md hover:bg-[var(--surface-dim)] transition-colors flex items-center gap-2 disabled:cursor-wait"
                              style={hasCustomTitle ? { color: "var(--text)" } : { fontStyle: "italic", fontWeight: 400 }}
                              title={isTitlePending ? "Titel wird generiert…" : hasCustomTitle ? "Titel ändern" : "Titel vergeben"}
                            >
                              <span className="flex-1 truncate">
                                {isTitlePending ? "Titel wird generiert…" : hasCustomTitle ? note.title : "Titel vergeben…"}
                              </span>
                              {isTitlePending
                                ? <Spinner size="xs" color="current" />
                                : <PencilSimple size={16} weight="bold" className="flex-shrink-0 opacity-60 group-hover:opacity-100 group-hover:text-[var(--kb)] group-focus:opacity-100 group-focus:text-[var(--kb)] transition-colors" />}
                            </button>
                          )
                        )}

                        <div className="text-sm ki-note-content" style={{ color: "var(--text)" }}>
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              p: ({ children }) => <p className="mb-2 last:mb-0">{wrapCitations(children)}</p>,
                              ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                              ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                              li: ({ children }) => <li className="leading-relaxed">{wrapCitations(children)}</li>,
                              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                              h1: ({ children }) => <p className="font-semibold mb-1">{wrapCitations(children)}</p>,
                              h2: ({ children }) => <p className="font-semibold mb-1">{wrapCitations(children)}</p>,
                              h3: ({ children }) => <p className="font-medium mb-1">{wrapCitations(children)}</p>,
                              table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-xs border-collapse">{children}</table></div>,
                              th: ({ children }) => <th className="text-left px-2 py-1 font-medium border-b" style={{ borderColor: "var(--border)" }}>{children}</th>,
                              td: ({ children }) => <td className="px-2 py-1 border-b" style={{ borderColor: "var(--border)" }}>{wrapCitations(children)}</td>,
                              hr: () => <hr className="my-3" style={{ borderColor: "var(--border)" }} />,
                            }}
                          >
                            {note.content.replace(/\[([^\]]*\|[^\]]*)\]/g, (m) => m.replace(/\|/g, "\u2758"))}
                          </ReactMarkdown>
                        </div>

                        {qmap.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
                            {qmap.map((s) => {
                              const ChipIcon = _getChipIcon(s.filename);
                              return (
                                <span
                                  key={s.qnum}
                                  role="button"
                                  tabIndex={0}
                                  onClick={(e) => { e.stopPropagation(); onChipClick(s.uuid, 0, s.filename); }}
                                  onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
                                  className="inline-flex items-center gap-1 text-[10px] cursor-pointer text-[var(--muted)] hover:text-[var(--accent)] transition-colors"
                                  title={s.filename}
                                >
                                  <ChipIcon size={10} weight="bold" />
                                  <span style={{ color: "var(--kb)" }}>[{s.qnum}]</span>
                                  <span className="max-w-[500px] truncate">{s.filename}</span>
                                </span>
                              );
                            })}
                          </div>
                        )}

                        <div className="flex items-center justify-between mt-3">
                          <span className="text-[10px]" >
                            {note.created_at ? new Date(note.created_at).toLocaleString("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onDelete(note.id); }}
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
          )}
        </div>
      </div>
    </div>
  );
}
