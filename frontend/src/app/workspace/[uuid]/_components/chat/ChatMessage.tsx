import { memo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CaretDown, CaretUp, Check, Copy, NotePencil } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Hilde, { type HildeState } from "@/components/ui/Hilde";
import { _embedQmapIntoCitations, _getChipIcon } from "../../_utils";
import type { ChatMessage as ChatMessageType } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { copyMessageText, withCitations, type CitationChipClickHandler } from "./_citations";


const SORRY_PATTERN = /nichts gefunden|keine information|in den quellen nicht enthalten|nicht in den (?:bereitgestellten |angegebenen )?quellen|kann ich nicht beantworten|steht nicht in den|not in the (?:provided |given )?sources?|no information (?:found|available|in)|could(?:n['']t| not) find|cannot find|is not (?:in|available in|contained in) (?:the )?sources?/i;


interface ChatMessageProps {
  msg: ChatMessageType;
  activeSourceIds: string[];
  getFilename: (uuid: string) => string;
  onChipClick: CitationChipClickHandler;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  loading: boolean;
  hildeEnabled?: boolean;
  isLatest?: boolean;
}


function ChatMessageImpl({
  msg, activeSourceIds, getFilename, onChipClick, onSaveNote, loading,
  hildeEnabled = false, isLatest = false,
}: ChatMessageProps) {
  const [expandUserContent, setExpandUserContent] = useState(false);
  const [expandSources, setExpandSources] = useState(false);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);
  const [savingNote, setSavingNote] = useState(false);

  const msgQmap = msg.source_qmap ?? [];
  const isUserLong = msg.content.split("\n").length > 5 || msg.content.length > 300;
  const wrapCitations = (children: React.ReactNode) =>
    withCitations(children, msg, activeSourceIds, getFilename, onChipClick);

  let avatarState: HildeState = "idle";
  if (msg.role === "assistant") {
    if (!msg.content && loading) {
      avatarState = "thinking";
    } else if (SORRY_PATTERN.test(msg.content)) {
      avatarState = "confused";
    } else if (isLatest && msgQmap.length > 0) {
      avatarState = "found";
    }
  }

  async function handleCopy() {
    try {
      await copyMessageText(msg.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error("Kopieren fehlgeschlagen", err);
    }
  }

  async function handleSaveNote() {
    if (!onSaveNote || savingNote) return;
    setSavingNote(true);
    try {
      await onSaveNote(
        _embedQmapIntoCitations(msg.content, msgQmap),
        msgQmap.map((q) => q.uuid),
        { sourcePages: msg.source_pages, popupSelection: msg.popup_selection ?? null },
      );
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } finally {
      setSavingNote(false);
    }
  }

  const actionButtons = (
    <>
      <button
        type="button"
        onClick={handleCopy}
        className="[@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 p-1 rounded-full btn-icon"
        title="Kopieren"
      >
        {copied ? <Check size={13} weight="bold" /> : <Copy size={13} />}
      </button>
      {msg.role === "assistant" && onSaveNote && !loading && (
        <button
          type="button"
          disabled={savingNote}
          onClick={handleSaveNote}
          className={`[@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 p-1 rounded-full ${saved ? "" : "btn-icon"}`}
          style={saved ? { color: "var(--success)" } : undefined}
          title="Als Notiz speichern"
        >
          {savingNote
            ? <Spinner size="xs" color="current" />
            : saved ? <Check size={13} weight="bold" /> : <NotePencil size={13} />}
        </button>
      )}
    </>
  );

  return (
    <div className={`flex flex-col gap-1.5 group ${msg.role === "user" ? "items-end" : "items-start"}`}>
      {msg.role === "assistant" && (
        hildeEnabled ? (
          isLatest && (
            <div className="flex items-center gap-2 mb-0.5">
              <Hilde size={80} state={avatarState} />
              <span className="text-lg font-medium">Hilde</span>
            </div>
          )
        ) : (
          <div className="flex items-center gap-2 mb-0.5">
            <div
              className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
              style={{ backgroundColor: "var(--kb)" }}
            >
              KI
            </div>
            <span className="text-lg font-medium">KI-Assistent</span>
          </div>
        )
      )}
      <div className="flex flex-col max-w-[96%] w-fit">
        <div
          className="px-4 py-3 rounded-2xl text-base leading-relaxed break-words"
          style={
            msg.role === "user"
              ? { backgroundColor: "var(--kb)", color: "white", borderBottomRightRadius: 6, whiteSpace: "pre-wrap", overflowWrap: "break-word" }
              : { backgroundColor: "var(--surface)", color: "var(--foreground)", border: "1px solid var(--border)", borderTopLeftRadius: 6, overflowWrap: "break-word" }
          }
        >
          {msg.role === "assistant" && !msg.content ? (
            <span className="inline-flex items-center gap-2">
              <span className="inline-flex gap-1">
                {[0, 1, 2].map((n) => (
                  <span
                    key={n}
                    className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
                    style={{ backgroundColor: "var(--muted)", animationDelay: `${n * 0.15}s` }}
                  />
                ))}
              </span>
            </span>
          ) : msg.role === "assistant" ? (
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
                table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-sm border-collapse">{children}</table></div>,
                thead: ({ children }) => <thead className="border-b border-current/20">{children}</thead>,
                th: ({ children }) => <th className="text-left px-2 py-1 font-semibold">{children}</th>,
                td: ({ children }) => <td className="px-2 py-1 border-t border-current/10">{wrapCitations(children)}</td>,
              }}
            >
              {msg.content.replace(/[[【]([^\]】]*\|[^\]】]*)[\]】]/g, (m) => m.replace(/\|/g, "❘"))}
            </ReactMarkdown>
          ) : (
            <>
              <div
                style={{
                  maxHeight: expandUserContent ? "none" : "8em",
                  overflow: "hidden",
                }}
              >
                {msg.content}
              </div>
              {isUserLong && (
                <button
                  type="button"
                  onClick={() => setExpandUserContent(v => !v)}
                  className="flex items-center gap-1 mt-1.5 text-xs opacity-70 hover:opacity-100 transition-opacity"
                  style={{ color: "white" }}
                >
                  {expandUserContent ? (
                    <><CaretUp size={12} /> Einklappen</>
                  ) : (
                    <><CaretDown size={12} /> Mehr anzeigen</>
                  )}
                </button>
              )}
            </>
          )}
        </div>

        {msg.role === "assistant" && msgQmap.length > 0 ? (
          <div className="mt-1 self-stretch">
            <div className="flex items-center justify-between w-full">
              <button
                type="button"
                onClick={() => setExpandSources(v => !v)}
                className="flex items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--kb)] transition-colors"
              >
                {expandSources ? <CaretUp size={10} /> : <CaretDown size={10} />}
                {msgQmap.length} {msgQmap.length === 1 ? "Quelle" : "Quellen"}
              </button>
              <div className="flex items-center gap-1">{actionButtons}</div>
            </div>
            {expandSources && (
              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 ml-3.5">
                {msgQmap.map((q) => {
                  const ChipIcon = _getChipIcon(q.filename);
                  return (
                    <span
                      key={q.qnum}
                      role="button"
                      tabIndex={0}
                      onClick={() => onChipClick(q.uuid, 0, q.filename)}
                      onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
                      className="inline-flex items-center gap-1 text-xs cursor-pointer text-[var(--muted)] hover:text-[var(--kb)] transition-colors"
                      title={q.filename}
                    >
                      <ChipIcon size={10} weight="bold" />
                      <span style={{ color: "var(--kb)" }}>[{q.qnum}]</span>
                      <span className="max-w-[500px] truncate">{q.filename}</span>
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <div className={`flex items-center gap-2 ${msg.role === "user" ? "flex-row-reverse" : "self-end"}`}>
            {actionButtons}
          </div>
        )}
      </div>
    </div>
  );
}

// React.memo: skip Markdown re-render when message + callbacks do not change.
// Noticeable on iPad, because otherwise ChatMessage re-runs ReactMarkdown +
// citation walk on every page.tsx re-render (e.g. tab switch).
export const ChatMessage = memo(ChatMessageImpl);
