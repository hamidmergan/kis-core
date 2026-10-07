import { memo, useLayoutEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { ArrowClockwise, Binoculars, CaretDown, CaretUp, Check, ChatCircle, Copy, FileText, FunnelSimple, Lightbulb, ListBullets, NotePencil, Stop, Translate, type Icon as PhosphorIconType } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Modal from "@/components/ui/Modal";
import { _embedQmapIntoCitations, _getChipIcon, _guardMathDollars } from "../../_utils";
import { KATEX_OPTIONS } from "../../_constants";
import type { ChatMessage as ChatMessageType } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { ChipToggleMark, copyMessageText, toggleAllChips, useAllChipsOpen, withCitations, type CitationChipClickHandler } from "./_citations";
import { hasCitations, sanitizeCitationsForMarkdown } from "./_citation_parse";
import ChatPhaseLine from "./ChatPhaseLine";


const POPUP_ACTION_ICONS: Record<string, PhosphorIconType> = {
  Translate,
  Lightbulb,
  Binoculars,
  FunnelSimple,
  ListBullets,
  ChatCircle,
};


// Two silent failure shapes of the translation are replaced by a message.
function _normalizeForCompare(s: string): string {
  return s.toLowerCase().replace(/[\s\p{P}\p{S}]+/gu, " ").trim();
}
function _isTranslateNoop(output: string, input: string | undefined): boolean {
  if (!input) return false;
  const out = _normalizeForCompare(output);
  if (!out) return false;
  const inp = _normalizeForCompare(input);
  if (out === inp) return true;
  return /^(laut quelle|laut material|according to the source)\b/.test(out);
}


// Only the part of a Markdown node the citations need.
type MarkdownNode = { position?: { start?: { offset?: number } } } | undefined;

interface ChatMessageProps {
  msg: ChatMessageType;
  // A stable name for the message so two never share a chip position.
  msgKey: string;
  activeSourceIds: string[];
  // Null when the workspace no longer holds the source.
  getFilename: (uuid: string) => string | null;
  onChipClick: CitationChipClickHandler;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  onRetry?: () => void;
  loading: boolean;
  isLatest?: boolean;
  collapseByDefault?: boolean;
  popupActions?: { key: string; label: string; icon: string }[];
  isAdmin?: boolean;
}


function ChatMessageImpl({
  msg, msgKey, activeSourceIds, getFilename, onChipClick, onSaveNote, onRetry, loading,
  isLatest = false, collapseByDefault = false,
  popupActions, isAdmin = false,
}: ChatMessageProps) {
  const t = useTranslations("workspace.detail.chat");
  const tChip = useTranslations("sourceChip");
  const [expandUserContent, setExpandUserContent] = useState(false);
  const [expandAssistantContent, setExpandAssistantContent] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  // The toggle reaches exactly the chip positions of this message.
  const allChipsOpen = useAllChipsOpen(msgKey);
  const [saved, setSaved] = useState(false);
  const [savingNote, setSavingNote] = useState(false);

  const msgQmap = msg.source_qmap ?? [];
  const assistantContentRef = useRef<HTMLDivElement | null>(null);
  const userContentRef = useRef<HTMLDivElement | null>(null);
  const [isAssistantOverflow, setIsAssistantOverflow] = useState(false);
  const [isUserOverflow, setIsUserOverflow] = useState(false);
  // The height is measured, citation markers inflate the text length.
  useLayoutEffect(() => {
    const el = msg.role === "assistant" ? assistantContentRef.current : userContentRef.current;
    if (!el) return;
    const check = () => {
      const fontSize = parseFloat(getComputedStyle(el).fontSize) || 16;
      const maxPx = 8 * fontSize;
      const overflow = el.scrollHeight > maxPx + 1;
      if (msg.role === "assistant") setIsAssistantOverflow(overflow);
      else setIsUserOverflow(overflow);
    };
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [msg.content, msg.role]);
  const collapseAssistant = collapseByDefault && msg.role === "assistant" && isAssistantOverflow && !expandAssistantContent;
  // Message plus position names a chip site unambiguously.
  const wrapCitations = (children: React.ReactNode, node?: MarkdownNode) =>
    withCitations(children, msg, activeSourceIds, getFilename, onChipClick,
      (key, vals) => tChip(key, vals), `${msgKey}#${node?.position?.start?.offset ?? 0}-`);
  // In table cells the text stays unchanged, no sentence ends there.
  const wrapCitationsInCell = (children: React.ReactNode, node?: MarkdownNode) =>
    withCitations(children, msg, activeSourceIds, getFilename, onChipClick,
      (key, vals) => tChip(key, vals), `${msgKey}#${node?.position?.start?.offset ?? 0}-`, false);


  const isTranslatePopup = msg.popup_selection?.action_key === "translate";
  const isStreaming = loading && isLatest;
  // Before the first word there is no bubble, the mascot shows the waiting.
  const waitingForFirstWord = msg.role === "assistant" && !msg.content && isStreaming;
  const translateFailed = msg.role === "assistant"
    && isTranslatePopup
    && !!msg.content
    && !isStreaming
    && _isTranslateNoop(msg.content, msg.popup_selection?.text);

  async function handleCopy() {
    try {
      await copyMessageText(msg.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error("Copy failed", err);
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

  // An empty answer has nothing to copy or save.
  const copyButton = (
    <button
      type="button"
      onClick={handleCopy}
      title={t("copy")}
      // A user message shows the icon only on hover and not on touch devices, an answer always.
      className={`w-7 h-7 flex items-center justify-center rounded-full btn-icon${msg.role === "user" ? " [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 [@media(hover:none)]:hidden" : ""}`}
    >
      {copied ? <Check size={14} weight="bold" /> : <Copy size={14} weight="bold" />}
    </button>
  );
  const actionButtons = msg.role === "assistant" && !msg.content ? null : (
    <>
      {msg.role === "assistant" && onSaveNote && !loading && (
        <button
          type="button"
          disabled={savingNote}
          onClick={handleSaveNote}
          className={`w-7 h-7 flex items-center justify-center rounded-full ${saved ? "" : "btn-icon"}`}
          style={saved ? { color: "var(--success)" } : undefined}
          title={t("saveAsNote")}
        >
          {savingNote
            ? <Spinner size="xs" color="current" />
            : saved ? <Check size={14} weight="bold" /> : <NotePencil size={14} weight="bold" />}
        </button>
      )}
      {msg.role === "assistant" && hasCitations(msg.content) && (
        <button
          type="button"
          onClick={() => toggleAllChips(msgKey)}
          aria-pressed={allChipsOpen}
          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          title={allChipsOpen ? t("hideAllCitations") : t("showAllCitations")}
        >
          <ChipToggleMark open={allChipsOpen} size={14} opacity={1} strokeWidth={0.63} />
        </button>
      )}
    </>
  );

  return (
    <div
      data-testid={msg.role === "assistant" ? "assistant-message" : "user-message"}
      className={`flex flex-col gap-1.5 group ${msg.role === "user" ? "items-end" : "items-start"}`}
    >
      {isAdmin && msg.role === "assistant" && msg.content && msg.applied_level ? (
        <span className="text-xs mb-0.5" style={{ color: "var(--muted-soft)" }}>
          {t("adaptiveLevel", { level: msg.applied_level })}
        </span>
      ) : null}
      <div className="flex flex-col max-w-[96%] w-fit">
        {waitingForFirstWord && (
          <ChatPhaseLine
            qmapArrived={msg.source_qmap !== undefined}
            isPopup={!!msg.popup_selection}
          />
        )}
        {!waitingForFirstWord && (
          <div
            className="px-4 py-2 rounded-2xl text-base leading-snug break-words"
            style={
              msg.role === "user"
                ? { backgroundColor: "var(--kb)", color: "white", borderBottomRightRadius: 6, whiteSpace: "pre-wrap", overflowWrap: "break-word" }
                : { backgroundColor: "var(--surface)", color: "var(--foreground)", borderTopLeftRadius: 6, overflowWrap: "break-word" }
            }
          >
            {msg.role === "assistant" && !msg.content ? (
              // After a reload a failed round has to say the same as it did live.
              <span className="text-xs italic" style={{ color: "var(--muted)" }}>
                {msg.failed ? t("genericError") : t("noAnswer")}
              </span>
            ) : msg.role === "assistant" && translateFailed ? (
              <span className="text-sm italic" style={{ color: "var(--muted)" }}>
                {t("translateFailed")}
              </span>
            ) : msg.role === "assistant" ? (
              <>
                <div
                  ref={assistantContentRef}
                  className={isStreaming ? "stream-cursor" : undefined}
                  style={collapseAssistant ? { maxHeight: "8em", overflow: "hidden" } : undefined}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[[rehypeKatex, KATEX_OPTIONS]]}
                    components={{
                      p: ({ node, children }) => <p className="mb-2 last:mb-0">{wrapCitations(children, node)}</p>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                      li: ({ node, children }) => <li className="leading-snug">{wrapCitations(children, node)}</li>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      h1: ({ node, children }) => <p className="font-semibold mb-1">{wrapCitations(children, node)}</p>,
                      h2: ({ node, children }) => <p className="font-semibold mb-1">{wrapCitations(children, node)}</p>,
                      h3: ({ node, children }) => <p className="font-medium mb-1">{wrapCitations(children, node)}</p>,
                      table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full min-w-[34rem] text-sm border-collapse">{children}</table></div>,
                      thead: ({ children }) => <thead className="border-b border-current/20">{children}</thead>,
                      th: ({ children }) => <th className="text-left px-2 py-1 font-semibold">{children}</th>,
                      td: ({ node, children }) => <td className="px-2 py-1 border-t border-current/10">{wrapCitationsInCell(children, node)}</td>,
                    }}
                  >
                    {_guardMathDollars(sanitizeCitationsForMarkdown(msg.content))}
                  </ReactMarkdown>
                </div>
                {collapseByDefault && isAssistantOverflow && (
                  <button
                    type="button"
                    onClick={() => setExpandAssistantContent(v => !v)}
                    className="flex items-center gap-1 mt-1.5 text-xs opacity-70 hover:opacity-100 transition-opacity"
                    style={{ color: "var(--muted)" }}
                  >
                    {expandAssistantContent ? (
                      <><CaretUp size={12} /> {t("collapse")}</>
                    ) : (
                      <><CaretDown size={12} /> {t("expand")}</>
                    )}
                  </button>
                )}
              </>
            ) : (() => {
              const actionKey = msg.popup_selection?.action_key;
              const actionIconName = msg.popup_selection?.action_icon;
              const ActionIcon = actionIconName ? POPUP_ACTION_ICONS[actionIconName] : undefined;
              const actionLabel = actionKey
                ? popupActions?.find((a) => a.key === actionKey)?.label ?? actionKey
                : undefined;
              const displayBody = actionKey
                ? (msg.popup_selection?.text ?? "")
                : msg.content;
              return (
                <>
                  {actionKey && (
                    <div className="flex items-center gap-1.5 text-sm font-medium mb-2 opacity-95">
                      {ActionIcon ? <ActionIcon size={14} weight="bold" /> : null}
                      <span>{actionLabel}</span>
                    </div>
                  )}
                  <div
                    ref={userContentRef}
                    className={actionKey ? "border-l-2 pl-2.5 italic text-sm opacity-95" : undefined}
                    style={{
                      maxHeight: expandUserContent ? "none" : "8em",
                      overflow: "hidden",
                      ...(actionKey ? { borderColor: "rgba(255,255,255,0.5)" } : {}),
                    }}
                  >
                    {displayBody}
                  </div>
                  {isUserOverflow && (
                    <button
                      type="button"
                      onClick={() => setExpandUserContent(v => !v)}
                      className="flex items-center gap-1 mt-1.5 text-xs opacity-70 hover:opacity-100 transition-opacity"
                      style={{ color: "white" }}
                    >
                      {expandUserContent ? (
                        <><CaretUp size={12} /> {t("collapse")}</>
                      ) : (
                        <><CaretDown size={12} /> {t("expand")}</>
                      )}
                    </button>
                  )}
                </>
              );
            })()}
          </div>
        )}

        {msg.role === "assistant" && msg.aborted && (
          <div className="flex items-center gap-1 mt-1 text-xs" style={{ color: "var(--muted)" }}>
            <Stop size={11} weight="bold" />
            <span>{t("aborted")}</span>
          </div>
        )}

        {/* Only the newest turn can be retried — an older failure is history, and
            re-asking it would land out of order below the newer conversation.
            Popup/action-bar turns are excluded: retryLast refuses to replay them
            (it needs the original selection context), so a button here would be a
            dead no-op. This mirrors retryLast's own guard. */}
        {msg.role === "assistant" && msg.failed && isLatest && !loading && onRetry && !msg.popup_selection && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 mt-1 text-xs text-[var(--muted)] hover:text-[var(--kb)] transition-colors"
          >
            <ArrowClockwise size={11} weight="bold" />
            <span>{t("retry")}</span>
          </button>
        )}

        {msg.role === "assistant" && !msg.content ? null : (
          <div className={`flex items-center ${msg.role === "user" ? "justify-end gap-1 mt-1" :"self-start flex-wrap gap-1.5 mt-2"}`}>
            <div className="flex items-center gap-1">
              {copyButton}
              {msg.role === "assistant" && actionButtons}
            </div>
            {msg.role === "assistant" && msgQmap.length > 0 && !isStreaming && (
              <button
                type="button"
                onClick={() => setSourcesOpen(true)}
                data-testid="chat-sources"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border-2 border-transparent bg-transparent text-xs min-w-0 max-w-full hover:border-kb focus:border-kb transition-colors"
                style={{ color: "var(--muted)" }}
              >
                <FileText size={14} weight="fill" style={{ color: "var(--muted)", flexShrink: 0 }} />
                <span>{t("sourcesCount", { n: msgQmap.length })}</span>
              </button>
            )}
          </div>
        )}
        {msg.role === "assistant" && msgQmap.length > 0 && (
          <Modal open={sourcesOpen} onClose={() => setSourcesOpen(false)} title={t("sourcesCount", { n: msgQmap.length })} size="md">
            <ul className="flex flex-col gap-2" data-testid="chat-sources-list">
              {msgQmap.map((q) => {
                const ChipIcon = _getChipIcon(q.filename);
                // A source removed since stays listed but opens nothing.
                const removed = getFilename(q.uuid) == null;
                return (
                  <li key={q.qnum}>
                    <button
                      type="button"
                      disabled={removed}
                      onClick={() => { setSourcesOpen(false); onChipClick(q.uuid, 0, q.filename); }}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl border-2 border-border text-left min-w-0 ${removed ? "opacity-50 cursor-not-allowed" : "hover:border-kb focus:border-kb transition-colors"}`}
                      title={removed ? `${q.filename}, ${tChip("removed")}` : q.filename}
                    >
                      <ChipIcon size={18} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
                      {msgQmap.length > 1 && <span className="text-sm" style={{ color: "var(--kb)" }}>[{q.qnum}]</span>}
                      <span className="text-sm font-medium break-words min-w-0 flex-1" style={{ color: "var(--foreground)" }}>{q.filename}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Modal>
        )}
      </div>
    </div>
  );
}

// Saves a redraw when message and callbacks do not change.
export const ChatMessage = memo(ChatMessageImpl);
