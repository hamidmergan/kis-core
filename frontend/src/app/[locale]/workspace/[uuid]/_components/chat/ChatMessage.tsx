import { memo, useLayoutEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { ArrowClockwise, Binoculars, CaretDown, CaretUp, Check, ChatCircle, Copy, FunnelSimple, Lightbulb, ListBullets, NotePencil, Stop, Translate, type Icon as PhosphorIconType } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Mascot, { type MascotState, type MascotVariant } from "@/components/ui/Mascot";
import { _embedQmapIntoCitations, _getChipIcon, _guardMathDollars } from "../../_utils";
import { KATEX_OPTIONS } from "../../_constants";
import type { ChatMessage as ChatMessageType } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { ChipToggleMark, copyMessageText, toggleAllChips, useAllChipsOpen, withCitations, type CitationChipClickHandler } from "./_citations";
import { hasCitations, sanitizeCitationsForMarkdown } from "./_citation_parse";


const POPUP_ACTION_ICONS: Record<string, PhosphorIconType> = {
  Translate,
  Lightbulb,
  Binoculars,
  FunnelSimple,
  ListBullets,
  ChatCircle,
};


// The refusal sentence comes at the end, the last patterns catch it.
const SORRY_PATTERN = /nichts gefunden|keine information|in den (?:quellen|materialien) nicht enthalten|nicht in den (?:bereitgestellten |angegebenen )?(?:quellen|materialien)|kann ich nicht beantworten|steht nicht in den|not in the (?:provided |given )?sources?|no information (?:found|available|in)|could(?:n['']t| not) find|cannot find|is not (?:in|available in|contained in) (?:the )?sources?|stehe?n nicht in den (?:quellen|materialien)|(?:is|are) not in the sources/i;

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
  getFilename: (uuid: string) => string;
  onChipClick: CitationChipClickHandler;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  onRetry?: () => void;
  loading: boolean;
  variant?: MascotVariant;
  isLatest?: boolean;
  collapseByDefault?: boolean;
  popupActions?: { key: string; label: string; icon: string }[];
  isAdmin?: boolean;
}


function ChatMessageImpl({
  msg, msgKey, activeSourceIds, getFilename, onChipClick, onSaveNote, onRetry, loading,
  variant = "francis", isLatest = false, collapseByDefault = false,
  popupActions, isAdmin = false,
}: ChatMessageProps) {
  const t = useTranslations("workspace.detail.chat");
  const tChip = useTranslations("sourceChip");
  const [expandUserContent, setExpandUserContent] = useState(false);
  const [expandAssistantContent, setExpandAssistantContent] = useState(false);
  const [expandSources, setExpandSources] = useState(false);
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

  let avatarState: MascotState = "idle";
  if (msg.role === "assistant") {
    // Thinking for the whole stream, the source numbers arrive earlier.
    if (isStreaming) {
      avatarState = "thinking";
    } else if (translateFailed || SORRY_PATTERN.test(msg.content)) {
      avatarState = "confused";
    } else if (isLatest && msgQmap.length > 0) {
      avatarState = "found";
    }
  }

  const streamingDots = (
    <span className="inline-flex gap-1 align-middle">
      {[0, 1, 2].map((n) => (
        <span
          key={n}
          className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
          style={{ backgroundColor: "var(--muted)", animationDelay: `${n * 0.15}s` }}
        />
      ))}
    </span>
  );

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
  const actionButtons = msg.role === "assistant" && !msg.content ? null : (
    <>
      {msg.role === "assistant" && hasCitations(msg.content) && (
        <button
          type="button"
          onClick={() => toggleAllChips(msgKey)}
          aria-pressed={allChipsOpen}
          // The toggle stays visible while it is on.
          className={`mt-1 p-1 rounded-full btn-icon${allChipsOpen ? "" : " [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100"}`}
          title={allChipsOpen ? t("hideAllCitations") : t("showAllCitations")}
        >
          <ChipToggleMark open={allChipsOpen} size={13} opacity={1} strokeWidth={0.63} />
        </button>
      )}
      <button
        type="button"
        onClick={handleCopy}
        className="mt-1 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 p-1 rounded-full btn-icon"
        title={t("copy")}
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
          title={t("saveAsNote")}
        >
          {savingNote
            ? <Spinner size="xs" color="current" />
            : saved ? <Check size={13} weight="bold" /> : <NotePencil size={13} />}
        </button>
      )}
    </>
  );

  return (
    <div
      data-testid={msg.role === "assistant" ? "assistant-message" : "user-message"}
      className={`flex flex-col gap-1.5 group ${msg.role === "user" ? "items-end" : "items-start"}`}
    >
      {msg.role === "assistant" && isLatest && (
        <div className="flex items-center gap-2 mb-0.5">
          <Mascot variant={variant} size={80} state={avatarState} />
          <span className="text-base font-medium">{variant === "hilde" ? t("hildeName") : t("francisName")}</span>
        </div>
      )}
      {isAdmin && msg.role === "assistant" && msg.content ? (
        <span className="text-xs mb-0.5" style={{ color: "var(--muted-soft)" }}>
          {msg.applied_level
            ? t("adaptiveLevel", { level: msg.applied_level })
            : t("adaptiveOff")}
        </span>
      ) : null}
      <div className="flex flex-col max-w-[96%] w-fit">
        {!waitingForFirstWord && (
          <div
            className="px-4 py-2 rounded-2xl text-base leading-snug break-words"
            style={
              msg.role === "user"
                ? { backgroundColor: "var(--kb)", color: "white", borderBottomRightRadius: 6, whiteSpace: "pre-wrap", overflowWrap: "break-word" }
                : { backgroundColor: "var(--surface)", color: "var(--foreground)", border: "1px solid var(--border)", borderTopLeftRadius: 6, overflowWrap: "break-word" }
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
                {isStreaming && <span className="inline-flex mt-1">{streamingDots}</span>}
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

        {msg.role === "assistant" && msgQmap.length > 0 ? (
          <div className="mt-1 self-stretch">
            <div className="flex items-center justify-between w-full">
              <button
                type="button"
                onClick={() => setExpandSources(v => !v)}
                className="flex items-center gap-1 text-xs text-[var(--muted)] hover-lighten transition-colors"
              >
                {expandSources ? <CaretUp size={10} /> : <CaretDown size={10} />}
                {t("sourcesCount", { n: msgQmap.length })}
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
                      className="inline-flex items-center gap-1 text-xs cursor-pointer text-[var(--muted)] hover-lighten transition-colors"
                      title={q.filename}
                    >
                      <ChipIcon size={10} weight="bold" />
                      {msgQmap.length > 1 && (
                        <span style={{ color: "var(--kb)" }}>[{q.qnum}]</span>
                      )}
                      <span className="max-w-125 truncate">{q.filename}</span>
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

// Saves a redraw when message and callbacks do not change.
export const ChatMessage = memo(ChatMessageImpl);
