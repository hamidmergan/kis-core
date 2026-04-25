import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CaretDown, CaretUp, Check, Copy, NotePencil } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { _embedQmapIntoCitations, _getChipIcon } from "../../_utils";
import type { ChatMessage as ChatMessageType } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { copyMessageText, withCitations, type CitationChipClickHandler } from "./_citations";


interface ChatMessageProps {
  msg: ChatMessageType;
  activeSourceIds: string[];
  getFilename: (uuid: string) => string;
  onChipClick: CitationChipClickHandler;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  loading: boolean;
}


export function ChatMessage({
  msg, activeSourceIds, getFilename, onChipClick, onSaveNote, loading,
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
        className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
        style={{ color: "var(--muted)" }}
        title="Kopieren"
      >
        {copied ? <Check size={13} weight="bold" /> : <Copy size={13} />}
      </button>
      {msg.role === "assistant" && onSaveNote && !loading && (
        <button
          type="button"
          disabled={savingNote}
          onClick={handleSaveNote}
          className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
          style={{ color: saved ? "#16a34a" : "var(--muted)" }}
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
        <div className="flex items-center gap-2 mb-0.5">
          <div
            className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
            style={{ backgroundColor: "var(--kb)" }}
          >
            KI
          </div>
          <span className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>
            KI-Assistent
          </span>
        </div>
      )}
      <div className="flex flex-col max-w-[96%] w-fit">
        <div
          className="px-4 py-3 rounded-2xl text-sm leading-relaxed break-words"
          style={
            msg.role === "user"
              ? { backgroundColor: "var(--kb)", color: "white", borderBottomRightRadius: 6, whiteSpace: "pre-wrap", overflowWrap: "break-word" }
              : { backgroundColor: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", borderTopLeftRadius: 6, overflowWrap: "break-word" }
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
                table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-xs border-collapse">{children}</table></div>,
                thead: ({ children }) => <thead className="border-b border-current/20">{children}</thead>,
                th: ({ children }) => <th className="text-left px-2 py-1 font-semibold">{children}</th>,
                td: ({ children }) => <td className="px-2 py-1 border-t border-current/10">{wrapCitations(children)}</td>,
              }}
            >
              {msg.content.replace(/\[([^\]]*\|[^\]]*)\]/g, (m) => m.replace(/\|/g, "❘"))}
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
                  className="flex items-center gap-1 mt-1.5 text-[11px] opacity-70 hover:opacity-100 transition-opacity"
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
                className="flex items-center gap-1 text-[10px] hover:opacity-80 transition-opacity"
                style={{ color: "var(--muted)" }}
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
                      className="inline-flex items-center gap-1 text-[10px] cursor-pointer hover:opacity-70 transition-opacity"
                      style={{ color: "var(--muted)" }}
                      title={q.filename}
                    >
                      <ChipIcon size={10} weight="bold" />
                      <span style={{ color: "var(--kb)" }}>[{q.qnum}]</span>
                      <span className="max-w-[160px] truncate">{q.filename}</span>
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
