import React, { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Chat,
  DotsThreeVertical,
  Trash,
  SidebarSimple,
  CaretDown,
  CaretUp,
  Copy,
  Check,
  NotePencil,
  PaperPlaneRight,
  X,
} from "@phosphor-icons/react";
import type { ChatMessage, Source } from "../_types";
import { _chunkLabel, _embedQmapIntoCitations, _getChipIcon } from "../_utils";
import Spinner from "@/components/ui/Spinner";

export function ChatPanel({
  messages,
  activeSourceIds,
  sources,
  loading,
  onSend,
  onPillClick,
  moduleReady,
  onClear,
  externalTextareaRef,
  onSaveNote,
  onMinimize,
  onSendPrompt,
  registerSetInput,
  hideHeader,
}: {
  messages: ChatMessage[];
  activeSourceIds: string[];
  sources: Source[];
  loading: boolean;
  onSend: (value: string) => void;
  onPillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
  moduleReady: boolean;
  onClear: () => void;
  externalTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  onSaveNote?: (content: string, sourceUuids?: string[]) => void | Promise<void>;
  onMinimize?: () => void;
  onSendPrompt?: (text: string) => void;
  registerSetInput?: (setter: ((v: string) => void) | null) => void;
  hideHeader?: boolean;
}) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const [expandedMsgs, setExpandedMsgs] = useState<Set<number>>(new Set());
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [savedNoteIdx, setSavedNoteIdx] = useState<number | null>(null);
  const [savingNoteIdx, setSavingNoteIdx] = useState<number | null>(null);

  async function handleSaveNote(idx: number, content: string, sourceUuids?: string[]) {
    if (!onSaveNote || savingNoteIdx !== null) return;
    setSavingNoteIdx(idx);
    try {
      await onSaveNote(content, sourceUuids);
      setSavedNoteIdx(idx);
      setTimeout(() => setSavedNoteIdx(null), 1500);
    } finally {
      setSavingNoteIdx(null);
    }
  }
  // Tracks window scroll on landscape mobile (inner scroll is disabled there)
  // to flip the jump button between "go to top" and "go to bottom".
  const [pageNearTop, setPageNearTop] = useState(true);
  const [pageScrollable, setPageScrollable] = useState(false);
  useEffect(() => {
    function update() {
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - window.innerHeight > 200;
      setPageScrollable(scrollable);
      setPageNearTop(window.scrollY < (doc.scrollHeight - window.innerHeight) / 2);
    }
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [messages.length]);
  function jumpPage() {
    if (pageNearTop) {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }
  const chatMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!chatMenuOpen) return;
    function handle(e: MouseEvent) {
      if (!chatMenuRef.current?.contains(e.target as Node)) setChatMenuOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [chatMenuOpen]);

  useEffect(() => {
    if (isFirstRender.current && messages.length > 0) {
      const c = scrollContainerRef.current;
      if (c) c.scrollTop = c.scrollHeight;
      isFirstRender.current = false;
    }
  }, [messages.length]);

  // Sticky-bottom auto-scroll: follow new content only while user is at the
  // bottom. If the user scrolls up mid-stream to re-read, stop following;
  // resume once they scroll back down.
  const stickBottomRef = useRef(true);
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    function onScroll() {
      if (!el) return;
      stickBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    }
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Snap to bottom when a new message is added (user just sent something).
  useEffect(() => {
    if (messages.length === 0) return;
    const el = scrollContainerRef.current;
    if (!el) return;
    stickBottomRef.current = true;
    el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  // Follow streaming content growth while sticky.
  useEffect(() => {
    const el = scrollContainerRef.current;
    const inner = el?.firstElementChild as HTMLElement | null;
    if (!el || !inner) return;
    const ro = new ResizeObserver(() => {
      if (stickBottomRef.current) el.scrollTop = el.scrollHeight;
    });
    ro.observe(inner);
    return () => ro.disconnect();
  }, []);

  const getFilename = (srcUuid: string) =>
    sources.find((s) => s.uuid === srcUuid)?.filename ?? srcUuid;

  // Wrap onPillClick so opening the viewer doesn't cause the chat to jump.
  // Captures scrollTop before the click and restores it across a few frames
  // while the panel layout settles.
  function handleChipClick(sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) {
    const el = scrollContainerRef.current;
    const savedTop = el?.scrollTop ?? 0;
    onPillClick(sourceUuid, page, filename, sourceText, startTime, isExact);
    if (el) {
      const restore = () => { el.scrollTop = savedTop; };
      requestAnimationFrame(() => { restore(); requestAnimationFrame(restore); });
      setTimeout(restore, 60);
    }
  }

  return (
    <div className="flex flex-col h-full chat-60vh">
      {pageScrollable && (
        <button
          type="button"
          onClick={jumpPage}
          aria-label={pageNearTop ? "Nach unten scrollen" : "Nach oben scrollen"}
          className="show-on-short fixed right-3 bottom-3 z-50 w-10 h-10 items-center justify-center rounded-full shadow-lg"
          style={{ backgroundColor: "var(--kb)", color: "white" }}
        >
          {pageNearTop ? <CaretDown size={18} weight="bold" /> : <CaretUp size={18} weight="bold" />}
        </button>
      )}
      {/* Header */}
      {!hideHeader && (
      <div className="flex items-center justify-between px-4 py-3 flex-shrink-0 relative" style={{ borderBottom: "1px solid var(--border)" }}>
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>Chat</span>
        <div className="flex items-center gap-1.5">
          <div className="relative" ref={chatMenuRef}>
            <button
              type="button"
              onClick={() => setChatMenuOpen((v) => !v)}
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
              title="Optionen"
            >
              <DotsThreeVertical size={16} weight="bold" />
            </button>
            {chatMenuOpen && (
              <div
                className="absolute right-0 top-8 z-50 rounded-xl py-1"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", minWidth: 220, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}
              >
                <button
                  type="button"
                  onClick={() => { onClear(); setChatMenuOpen(false); }}
                  disabled={messages.length === 0}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 disabled:opacity-40 transition-colors"
                  style={{ color: "#B91C1C" }}
                >
                  <Trash size={16} />
                  Chatprotokoll löschen
                </button>
              </div>
            )}
          </div>
          {onMinimize && (
            <button
              type="button"
              onClick={onMinimize}
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
              title="Panel minimieren"
            >
              <SidebarSimple size={13} />
            </button>
          )}
        </div>
      </div>
      )}

      {/* Messages */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full p-3 flex flex-col gap-5" style={{ maxWidth: 720 }}>
          {messages.length === 0 && !loading && (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 py-16">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center"
                style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)" }}
              >
                <Chat size={22} style={{ color: "var(--kb)" }} />
              </div>
              <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
                Dein KI-Assistent
              </p>
              <p className="text-xs text-center max-w-xs" style={{ color: "var(--muted)" }}>
                Wähle Quellen links aus – stell Fragen, lass dir Inhalte erklären oder gib Anweisungen.
              </p>
              <div className="flex flex-col gap-2 mt-2 w-full max-w-sm">
                {[
                  "Gib mir einen Überblick über den Inhalt.",
                  "Fasse die wichtigsten Punkte zusammen.",
                  "Erkläre zentrale Begriffe kurz und verständlich.",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    disabled={activeSourceIds.length === 0}
                    onClick={() => onSendPrompt?.(prompt)}
                    className="text-left text-xs px-4 rounded-xl border transition-all"
                    style={{
                      height: 50,
                      borderColor: activeSourceIds.length === 0 ? "var(--border)" : "rgba(var(--kb-rgb),0.25)",
                      color: activeSourceIds.length === 0 ? "var(--muted)" : "var(--text)",
                      backgroundColor: "transparent",
                      cursor: activeSourceIds.length === 0 ? "default" : "pointer",
                      opacity: activeSourceIds.length === 0 ? 0.5 : 1,
                    }}
                    onMouseEnter={(e) => {
                      if (activeSourceIds.length > 0) {
                        e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb),0.10)";
                        e.currentTarget.style.borderColor = "rgba(var(--kb-rgb),0.4)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (activeSourceIds.length > 0) {
                        e.currentTarget.style.backgroundColor = "transparent";
                        e.currentTarget.style.borderColor = "rgba(var(--kb-rgb),0.25)";
                      }
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => {
            const msgSourcePages = msg.source_pages ?? [];
            const msgQmap = msg.source_qmap ?? [];
            let chipKeyCounter = 0;
            function parseCitations(text: string): React.ReactNode[] {
              // Matches [1, S. 2 | kw], [Q1, S. 2 | kw], [S. 2], [1, 05:32 | kw] (Q prefix optional for backwards compat)
              const pattern = /\[(?:Q?(\d+),\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))(?:\s*[|\u2758]\s*([^\]]+))?\s*\]/g;
              const nodes: React.ReactNode[] = [];
              let last = 0;
              let m: RegExpExecArray | null;
              while ((m = pattern.exec(text)) !== null) {
                if (m.index > last) nodes.push(text.slice(last, m.index));
                const qNum = m[1] ? parseInt(m[1]) : null;
                const pageNum = m[2] ? parseInt(m[2]) : 0;
                const timestamp = m[3] || null;
                const keywords = m[4]?.trim().replace(/^["']+|["']+$/g, "").trim() || null;
                const qEntry = qNum ? msgQmap.find(q => q.qnum === qNum) : null;
                const sourceUuid = qEntry?.uuid ?? msgSourcePages[0]?.source_uuid ?? activeSourceIds[0] ?? "";
                const filename = qEntry?.filename ?? getFilename(sourceUuid);
                // Fallback: qnum aus qmap via sourceUuid (z.B. bei Popup-Aktionen ohne Q-Prefix)
                const displayQNum = qNum ?? msgQmap.find(q => q.uuid === sourceUuid)?.qnum ?? null;
                const label = timestamp || _chunkLabel(filename, pageNum);
                const ck = `c${chipKeyCounter++}`;
                let seconds = 0;
                if (timestamp) {
                  const tp = timestamp.split(":").map(Number);
                  seconds = tp.length === 3 ? tp[0] * 3600 + tp[1] * 60 + tp[2] : tp[0] * 60 + tp[1];
                }
                const clickUuid = sourceUuid;
                const clickPage = pageNum;
                const clickFile = filename;
                // Popup-Aktionen: markierter Text als Highlight nutzen
                const popupEntry = msgSourcePages.find(s => s.is_popup_selection && s.source_uuid === sourceUuid && s.page_number === pageNum);
                const popupSel = msg.popup_selection;
                const matchesPopupSel = popupSel && popupSel.uuid === sourceUuid && popupSel.page === pageNum;
                const clickHighlight = popupEntry?.source_text
                  ? popupEntry.source_text
                  : matchesPopupSel
                    ? popupSel!.text
                    : (keywords || undefined);
                const isExactSelection = !!(popupEntry?.source_text || matchesPopupSel);
                const clickSeconds = timestamp ? seconds : undefined;
                const ChipIcon = _getChipIcon(filename);
                nodes.push(
                  <span key={ck} role="button" tabIndex={0}
                    // onPointerDown (statt onClick), damit Chips auch während aktivem Token-Stream
                    // klickbar bleiben: bei onClick unmountet react-markdown den Chip zwischen
                    // down und up oft, sodass der native Click auf dem Vorfahren landet.
                    // Pointer (statt Mouse), damit Touch-Geraete den Handler zuverlaessig triggern.
                    onPointerDown={(e) => { if (e.button === 0) handleChipClick(clickUuid, clickSeconds ? 0 : clickPage, clickFile, clickSeconds ? undefined : clickHighlight, clickSeconds, isExactSelection); }}
                    onKeyDown={(e) => { if (e.key === "Enter") handleChipClick(clickUuid, clickSeconds ? 0 : clickPage, clickFile, clickSeconds ? undefined : clickHighlight, clickSeconds, isExactSelection); }}
                    className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity align-middle mx-0.5 cursor-pointer"
                    style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
                    title={`${filename}, ${label}`}
                  ><ChipIcon size={8} weight="bold" />{displayQNum ? `[${displayQNum}] ` : ""}{label}</span>
                );
                last = pattern.lastIndex;
              }
              if (last < text.length) nodes.push(text.slice(last));
              return nodes;
            }

            function withCitations(children: React.ReactNode): React.ReactNode {
              const arr: React.ReactNode[] = Array.isArray(children) ? children : [children];
              return arr.flatMap((child) =>
                typeof child === "string" ? parseCitations(child) : [child]
              );
            }

            return (
              <div
                key={msg.id ?? i}
                className={`flex flex-col gap-1.5 group ${msg.role === "user" ? "items-end" : "items-start"}`}
              >
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
                        p: ({ children }) => <p className="mb-2 last:mb-0">{withCitations(children)}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                        li: ({ children }) => <li className="leading-relaxed">{withCitations(children)}</li>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        h1: ({ children }) => <p className="font-semibold mb-1">{withCitations(children)}</p>,
                        h2: ({ children }) => <p className="font-semibold mb-1">{withCitations(children)}</p>,
                        h3: ({ children }) => <p className="font-medium mb-1">{withCitations(children)}</p>,
                        table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-xs border-collapse">{children}</table></div>,
                        thead: ({ children }) => <thead className="border-b border-current/20">{children}</thead>,
                        th: ({ children }) => <th className="text-left px-2 py-1 font-semibold">{children}</th>,
                        td: ({ children }) => <td className="px-2 py-1 border-t border-current/10">{withCitations(children)}</td>,
                      }}
                    >
                      {msg.content.replace(/\[([^\]]*\|[^\]]*)\]/g, (m) => m.replace(/\|/g, "\u2758"))}
                    </ReactMarkdown>
                  ) : (
                    <>
                      <div
                        style={{
                          maxHeight: expandedMsgs.has(i) ? "none" : "8em",
                          overflow: "hidden",
                        }}
                      >
                        {msg.content}
                      </div>
                      {msg.content.split("\n").length > 5 || msg.content.length > 300 ? (
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedMsgs((prev) => {
                              const next = new Set(prev);
                              next.has(i) ? next.delete(i) : next.add(i);
                              return next;
                            })
                          }
                          className="flex items-center gap-1 mt-1.5 text-[11px] opacity-70 hover:opacity-100 transition-opacity"
                          style={{ color: "white" }}
                        >
                          {expandedMsgs.has(i) ? (
                            <>
                              <CaretUp size={12} /> Einklappen
                            </>
                          ) : (
                            <>
                              <CaretDown size={12} /> Mehr anzeigen
                            </>
                          )}
                        </button>
                      ) : null}
                    </>
                  )}
                </div>
                {msg.role === "assistant" && msgQmap.length > 0 ? (
                  <div className="mt-1 self-stretch">
                    <div className="flex items-center justify-between w-full">
                      <button
                        type="button"
                        onClick={() => setExpandedMsgs((prev) => {
                          const next = new Set(prev);
                          const key = i + 10000;
                          next.has(key) ? next.delete(key) : next.add(key);
                          return next;
                        })}
                        className="flex items-center gap-1 text-[10px] hover:opacity-80 transition-opacity"
                        style={{ color: "var(--muted)" }}
                      >
                        {expandedMsgs.has(i + 10000) ? <CaretUp size={10} /> : <CaretDown size={10} />}
                        {msgQmap.length} {msgQmap.length === 1 ? "Quelle" : "Quellen"}
                      </button>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={async () => {
                            const text = msg.content.replace(/\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\|[^\]]+)?\]/g, "").trim();
                            try {
                              if (navigator.clipboard?.writeText && window.isSecureContext) {
                                await navigator.clipboard.writeText(text);
                              } else {
                                const ta = document.createElement("textarea");
                                ta.value = text;
                                ta.setAttribute("readonly", "");
                                ta.style.position = "fixed";
                                ta.style.opacity = "0";
                                document.body.appendChild(ta);
                                ta.select();
                                document.execCommand("copy");
                                document.body.removeChild(ta);
                              }
                              setCopiedIdx(i);
                              setTimeout(() => setCopiedIdx(null), 1500);
                            } catch (err) {
                              console.error("Kopieren fehlgeschlagen", err);
                            }
                          }}
                          className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
                          style={{ color: "var(--muted)" }}
                          title="Kopieren"
                        >
                          {copiedIdx === i ? <Check size={13} weight="bold" /> : <Copy size={13} />}
                        </button>
                        {onSaveNote && !loading && (
                          <button
                            type="button"
                            disabled={savingNoteIdx === i}
                            onClick={() => handleSaveNote(i, _embedQmapIntoCitations(msg.content, msg.source_qmap ?? []), (msg.source_qmap ?? []).map((q) => q.uuid))}
                            className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
                            style={{ color: savedNoteIdx === i ? "#16a34a" : "var(--muted)" }}
                            title="Als Notiz speichern"
                          >
                            {savingNoteIdx === i
                              ? <Spinner size="xs" color="current" />
                              : savedNoteIdx === i ? <Check size={13} weight="bold" /> : <NotePencil size={13} />}
                          </button>
                        )}
                      </div>
                    </div>
                    {expandedMsgs.has(i + 10000) && (
                      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 ml-3.5">
                        {msgQmap.map((q) => {
                          const ChipIcon = _getChipIcon(q.filename);
                          return (
                            <span
                              key={q.qnum}
                              role="button"
                              tabIndex={0}
                              onClick={() => handleChipClick(q.uuid, 0, q.filename)}
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
                    <button
                      type="button"
                      onClick={async () => {
                        const text = msg.content.replace(/\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\|[^\]]+)?\]/g, "").trim();
                        try {
                          if (navigator.clipboard?.writeText && window.isSecureContext) {
                            await navigator.clipboard.writeText(text);
                          } else {
                            const ta = document.createElement("textarea");
                            ta.value = text;
                            ta.setAttribute("readonly", "");
                            ta.style.position = "fixed";
                            ta.style.opacity = "0";
                            document.body.appendChild(ta);
                            ta.select();
                            document.execCommand("copy");
                            document.body.removeChild(ta);
                          }
                          setCopiedIdx(i);
                          setTimeout(() => setCopiedIdx(null), 1500);
                        } catch (err) {
                          console.error("Kopieren fehlgeschlagen", err);
                        }
                      }}
                      className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
                      style={{ color: "var(--muted)" }}
                      title="Kopieren"
                    >
                      {copiedIdx === i ? <Check size={13} weight="bold" /> : <Copy size={13} />}
                    </button>
                    {msg.role === "assistant" && onSaveNote && !loading && (
                      <button
                        type="button"
                        disabled={savingNoteIdx === i}
                        onClick={() => handleSaveNote(i, _embedQmapIntoCitations(msg.content, msg.source_qmap ?? []), (msg.source_qmap ?? []).map((q) => q.uuid))}
                        className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
                        style={{ color: savedNoteIdx === i ? "#16a34a" : "var(--muted)" }}
                        title="Als Notiz speichern"
                      >
                        {savingNoteIdx === i
                          ? <Spinner size="xs" color="current" />
                          : savedNoteIdx === i ? <Check size={13} weight="bold" /> : <NotePencil size={13} />}
                      </button>
                    )}
                  </div>
                )}
                </div>
              </div>
            );
          })}

          {/* Loading indicator removed – streaming messages show inline dots */}
        </div>
      </div>

      <ChatInputBar
        loading={loading}
        activeSourceIds={activeSourceIds}
        onSend={onSend}
        externalTextareaRef={externalTextareaRef}
        registerSetInput={registerSetInput}
      />
      <p className="hide-on-short w-full text-center mt-3 pb-0 text-[10px]" style={{ color: "var(--muted)", opacity: 0.5 }}>
        Diese Plattform nutzt KI und kann Fehler machen. Überprüfen Sie die Antworten.
      </p>
      <p className="hide-on-short w-full text-center mt-1 pb-2 text-[10px]" style={{ color: "var(--muted)", opacity: 0.5 }}>
        Feedback oder Probleme?{" "}
        <a href="mailto:hamid.mergan@th-luebeck.de" className="underline hover:opacity-100 transition-opacity">
          hamid.mergan@th-luebeck.de
        </a>
      </p>
    </div>
  );
}

function ChatInputBar({
  loading,
  activeSourceIds,
  onSend,
  externalTextareaRef,
  registerSetInput,
}: {
  loading: boolean;
  activeSourceIds: string[];
  onSend: (value: string) => void;
  externalTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  registerSetInput?: (setter: ((v: string) => void) | null) => void;
}) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const textareaCallbackRef = useCallback((el: HTMLTextAreaElement | null) => {
    (textareaRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
    if (externalTextareaRef) (externalTextareaRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
  }, [externalTextareaRef]);
  useEffect(() => {
    registerSetInput?.(setInput);
    return () => registerSetInput?.(null);
  }, [registerSetInput]);
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [input]);
  const submit = useCallback(() => {
    const value = input;
    if (!value.trim()) return;
    onSend(value);
    setInput("");
  }, [input, onSend]);
  return (
    <div
      className="flex-shrink-0 px-6 pt-2 pb-0"
      style={{ borderTop: "1px solid var(--border)" }}
    >
      <div className="mx-auto w-full" style={{ maxWidth: 720 }}>
        <div className="flex justify-end px-1 mb-1">
          <span className="text-[10px] leading-none" style={{ color: "var(--muted)" }}>
            {activeSourceIds.length} {activeSourceIds.length === 1 ? "Quelle" : "Quellen"} aktiv
          </span>
        </div>
        <div
          className="flex items-center gap-2 rounded-2xl px-4 py-3"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <textarea
            ref={textareaCallbackRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
            }}
            placeholder="Text eingeben…"
            rows={1}
            disabled={loading}
            className="flex-1 text-sm resize-none focus:outline-none disabled:opacity-50 bg-transparent"
            style={{ color: "var(--text)", maxHeight: 160, overflowY: "auto" }}
          />
          {input && (
            <button
              type="button"
              onClick={() => { setInput(""); textareaRef.current?.focus(); }}
              className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ color: "var(--muted)" }}
              title="Eingabe löschen"
            >
              <X size={14} weight="bold" />
            </button>
          )}
          <button
            type="button"
            onClick={submit}
            disabled={loading || !input.trim() || activeSourceIds.length === 0}
            className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl text-white disabled:opacity-40 transition-opacity hover:opacity-85"
            style={{ backgroundColor: "var(--kb)" }}
            title="Senden"
          >
            <PaperPlaneRight size={16} weight="bold" />
          </button>
        </div>
      </div>
    </div>
  );
}
