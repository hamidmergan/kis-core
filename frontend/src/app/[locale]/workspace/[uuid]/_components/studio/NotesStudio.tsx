import React, { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { CaretDown, CaretUp, NotePencil, PencilSimple, Plus, Trash, X } from "@phosphor-icons/react";
import type { ChatMessage, Source, SourceQmap, SourceRef } from "../../_types";
import { _getChipIcon, _guardMathDollars, _mathToUnicode } from "../../_utils";
import { withCitations, type CitationChipClickHandler } from "../chat/_citations";
import { SubviewHeader, type BreadcrumbItem } from "../layout/SubviewHeader";
import { StudioSourceLegend } from "./StudioSourceLegend";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import Modal from "@/components/ui/Modal";
import { NOTE_TITLE_MAX, NOTE_BODY_MAX, NOTE_BODY_WARN_AT, KATEX_OPTIONS } from "../../_constants";

export interface Note {
  id: number;
  title?: string | null;
  content: string;
  source_uuids?: string[] | null;
  source_pages?: SourceRef[] | null;
  popup_selection?: { uuid: string; page: number; text: string } | null;
  created_at: string | null;
}

function _notePreview(content: string, emptyLabel: string, max = 60): string {
  const stripped = _mathToUnicode(content)
    .replace(/\[[^\]]*\]/g, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#+\s+/gm, "")
    .replace(/^\s*[->*+]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!stripped) return emptyLabel;
  return stripped.length > max ? stripped.slice(0, max).trimEnd() + "…" : stripped;
}

export function NotesStudio({
  notes, onAdd, onDelete, onUpdateTitle, onBack, sources, activeSourceIds, onPillClick, breadcrumbs, pendingTitleIds,
}: {
  notes: Note[]; onAdd: (content: string) => void; onDelete: (id: number) => void;
  onUpdateTitle?: (id: number, title: string | null) => void;
  onBack?: () => void;
  sources?: Source[]; activeSourceIds?: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
  breadcrumbs?: BreadcrumbItem[];
  pendingTitleIds?: Set<number>;
}) {
  const t = useTranslations("workspace.detail.studio.notes");
  const tChip = useTranslations("sourceChip");
  const locale = useLocale();
  const [draft, setDraft] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [renameNoteId, setRenameNoteId] = useState<number | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function commitRename() {
    if (renameNoteId == null) return;
    const current = notes.find((n) => n.id === renameNoteId);
    const clean = renameDraft.trim();
    const next = clean === "" ? null : clean;
    if ((current?.title ?? null) !== next) onUpdateTitle?.(renameNoteId, next);
    setRenameNoteId(null);
  }

  const getFilename = (uuid: string) => sources?.find(s => s.uuid === uuid)?.filename ?? uuid;
  const onChipClick: CitationChipClickHandler = (uuid, page, filename, sourceText, startTime, isExact) =>
    onPillClick?.(uuid, page, filename, sourceText, startTime, isExact);

  // Builds a chat message object so the citation display can be reused.
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
      {onBack && <SubviewHeader title={t("title")} toolKey="Notes" onBack={onBack} breadcrumbs={breadcrumbs} />}
      <div className="flex-1 overflow-y-auto">
        <div className="w-full px-4 pt-4 pb-6 flex flex-col gap-3">
          {/* New note input */}
          <div
            className="mx-auto w-full flex gap-2 items-center rounded-xl p-2 border-2 border-[var(--border)] hover:border-[var(--kb)] focus-within:border-[var(--kb)] transition-colors"
            style={{ maxWidth: 640, backgroundColor: "var(--background)" }}
          >
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => { if (e.target.value.length <= NOTE_BODY_MAX) setDraft(e.target.value); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && draft.trim()) { e.preventDefault(); onAdd(draft.trim()); setDraft(""); }
              }}
              placeholder={t("placeholder")}
              maxLength={NOTE_BODY_MAX}
              rows={1}
              className="flex-1 text-base resize-none focus:outline-none bg-transparent"
              style={{ color: "var(--foreground)", maxHeight: 160, overflowY: "auto" }}
            />
            {draft.length > NOTE_BODY_WARN_AT && (
              <span className="text-xs flex-shrink-0" style={{ color: draft.length >= NOTE_BODY_MAX ? "var(--error)" : "var(--muted)" }}>
                {draft.length}/{NOTE_BODY_MAX}
              </span>
            )}
            {draft && (
              <button
                type="button"
                onClick={() => { setDraft(""); textareaRef.current?.focus(); }}
                className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full btn-icon"
                title={t("clearInput")}
              >
                <X size={14} weight="bold" />
              </button>
            )}
            <button
              type="button"
              onClick={() => { if (draft.trim()) { onAdd(draft.trim()); setDraft(""); } }}
              disabled={!draft.trim()}
              className="btn-fill-accent flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg disabled:opacity-40 transition-colors"
              title={t("save")}
            >
              <Plus size={14} weight="bold" />
            </button>
          </div>

          {/* Empty state */}
          {notes.length === 0 && (
            <EmptyState
              icon={<NotePencil size={32} weight="bold" />}
              text={t("empty")}
            />
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
                // Note plus node position names a chip site unambiguously.
                const wrapCitations = (
                  children: React.ReactNode,
                  node?: { position?: { start?: { offset?: number } } },
                ) =>
                  withCitations(children, msg, activeSourceIds ?? [], getFilename, onChipClick,
                    (key, vals) => tChip(key, vals), `n${note.id}#${node?.position?.start?.offset ?? 0}-`);
                // In table cells the text stays unchanged.
                const wrapCitationsInCell = (
                  children: React.ReactNode,
                  node?: { position?: { start?: { offset?: number } } },
                ) =>
                  withCitations(children, msg, activeSourceIds ?? [], getFilename, onChipClick,
                    (key, vals) => tChip(key, vals), `n${note.id}#${node?.position?.start?.offset ?? 0}-`, false);
                const isLast = idx === notes.length - 1;
                const hasCustomTitle = !!(note.title && note.title.trim());
                const isTitlePending = !hasCustomTitle && !!pendingTitleIds?.has(note.id);
                const rowLabel = hasCustomTitle ? note.title!.trim() : _notePreview(note.content, t("emptyPreview"));

                return (
                  <div key={note.id} style={{ borderBottom: isLast && !isExpanded ? "none" : "1px solid var(--border)" }}>
                    {/* Row */}
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => setExpandedId(isExpanded ? null : note.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setExpandedId(isExpanded ? null : note.id); } }}
                      className="row-expandable flex items-center gap-3 px-3 cursor-pointer hover:bg-[var(--surface-dim)] transition-colors"
                      style={{ minHeight: 48, color: "var(--foreground)" }}
                    >
                      <span
                        className="flex-1 text-base truncate flex items-center gap-2"
                        style={hasCustomTitle ? { fontWeight: 500 } : { fontStyle: "italic" }}
                      >
                        {isTitlePending && <Spinner size="xs" color="current" />}
                        <span className="truncate">{rowLabel}</span>
                      </span>
                      <span className="flex-shrink-0 text-xs text-[var(--muted)]">
                        {note.created_at ? new Date(note.created_at).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", { day: "numeric", month: "short", timeZone: "Europe/Berlin" }) : ""}
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
                        <div className="text-base ki-note-content" style={{ color: "var(--foreground)" }}>
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm, remarkMath]}
                            rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
                            components={{
                              p: ({ node, children }) => <p className="mb-2 last:mb-0">{wrapCitations(children, node)}</p>,
                              ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                              ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                              li: ({ node, children }) => <li className="leading-relaxed">{wrapCitations(children, node)}</li>,
                              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                              em: ({ children }) => <em style={{ color: "var(--muted)" }}>{children}</em>,
                              h1: ({ node, children }) => <p className="font-semibold mb-1">{wrapCitations(children, node)}</p>,
                              h2: ({ node, children }) => <p className="font-semibold mb-1">{wrapCitations(children, node)}</p>,
                              h3: ({ node, children }) => <p className="font-medium mb-1">{wrapCitations(children, node)}</p>,
                              table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-sm border-collapse">{children}</table></div>,
                              th: ({ children }) => <th className="text-left px-2 py-1 font-medium border-b" style={{ borderColor: "var(--border)" }}>{children}</th>,
                              td: ({ node, children }) => <td className="px-2 py-1 border-b" style={{ borderColor: "var(--border)" }}>{wrapCitationsInCell(children, node)}</td>,
                              hr: () => <hr className="my-3" style={{ borderColor: "var(--border)" }} />,
                            }}
                          >
                            {_guardMathDollars(note.content.replace(/[[\u3010]([^\]\u3011]*\|[^\]\u3011]*)[\]\u3011]/g, (m) => m.replace(/\|/g, "\u2758")))}
                          </ReactMarkdown>
                        </div>

                        {qmap.length > 0 && (
                          <StudioSourceLegend
                            count={qmap.length}
                            className="mt-3"
                            listClassName="flex flex-wrap gap-x-3 gap-y-1 pl-4"
                          >
                            {qmap.map((s) => {
                              const ChipIcon = _getChipIcon(s.filename);
                              return (
                                <span
                                  key={s.qnum}
                                  role="button"
                                  tabIndex={0}
                                  onClick={(e) => { e.stopPropagation(); onChipClick(s.uuid, 0, s.filename); }}
                                  onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
                                  className="inline-flex items-center gap-1 text-xs cursor-pointer text-[var(--muted)] hover-lighten transition-colors"
                                  title={s.filename}
                                >
                                  <ChipIcon size={10} weight="bold" />
                                  <span style={{ color: "var(--kb)" }}>[{s.qnum}]</span>
                                  <span className="max-w-125 truncate">{s.filename}</span>
                                </span>
                              );
                            })}
                          </StudioSourceLegend>
                        )}

                        <div className="flex items-center justify-between mt-3">
                          <span className="text-xs" >
                            {note.created_at ? new Date(note.created_at).toLocaleString("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                          </span>
                          <div className="flex items-center gap-1.5">
                            {onUpdateTitle && (
                              <button
                                type="button"
                                disabled={isTitlePending}
                                onClick={(e) => { e.stopPropagation(); setRenameDraft(note.title ?? ""); setRenameNoteId(note.id); }}
                                className="w-6 h-6 rounded-full flex items-center justify-center btn-icon disabled:opacity-40 disabled:cursor-wait"
                                style={{ backgroundColor: "var(--surface-dim)" }}
                                title={isTitlePending ? t("titleGenerating") : t("titleEdit")}
                                aria-label={t("titleEdit")}
                              >
                                <PencilSimple size={12} />
                              </button>
                            )}
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
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <Modal
        open={renameNoteId !== null}
        onClose={() => setRenameNoteId(null)}
        title={t("titleEdit")}
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setRenameNoteId(null)}
              className="btn-cancel px-4 py-2 rounded-lg text-sm font-semibold text-[var(--muted)] bg-[var(--surface-dim)]"
            >
              {t("cancel")}
            </button>
            <button
              type="button"
              onClick={commitRename}
              className="btn-fill-accent px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
            >
              {t("titleSave")}
            </button>
          </div>
        }
      >
        <input
          autoFocus
          type="text"
          value={renameDraft}
          onChange={(e) => setRenameDraft(e.target.value.slice(0, NOTE_TITLE_MAX))}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); commitRename(); } }}
          placeholder={t("titlePlaceholder")}
          maxLength={NOTE_TITLE_MAX}
          className="w-full text-base font-medium px-2 py-1 rounded-md focus:outline-none"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--foreground)", border: "1px solid var(--border)" }}
        />
      </Modal>
    </div>
  );
}
