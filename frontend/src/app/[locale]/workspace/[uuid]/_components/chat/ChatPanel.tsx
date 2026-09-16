import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretDown, CaretUp } from "@phosphor-icons/react";
import type { ChatMessage as ChatMessageType, Source } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { useMascotPref } from "@/hooks/useMascotPref";
import { ChatHeader } from "./ChatHeader";
import { ChatEmptyState } from "./ChatEmptyState";
import { ChatMessage } from "./ChatMessage";
import { ChatInputBar } from "./ChatInputBar";
import IconButton from "@/components/ui/IconButton";


export function ChatPanel({
  messages,
  activeSourceIds,
  sources,
  popupActions,
  loading,
  onSend,
  onStop,
  onPillClick,
  onClear,
  externalTextareaRef,
  onSaveNote,
  onRetry,
  onMinimize,
  onSendPrompt,
  registerSetInput,
  hideHeader,
  isAdmin,
}: {
  messages: ChatMessageType[];
  activeSourceIds: string[];
  sources: Source[];
  popupActions?: { key: string; label: string; icon: string; prompt: string; min_words: number }[];
  loading: boolean;
  onSend: (value: string) => void;
  onStop?: () => void;
  onPillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean, hideTranscript?: boolean, endTime?: number, chunkStart?: number) => void;
  moduleReady: boolean;
  onClear: () => void;
  externalTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  onRetry?: () => void;
  onMinimize?: () => void;
  onSendPrompt?: (text: string) => void;
  registerSetInput?: (setter: ((v: string) => void) | null) => void;
  hideHeader?: boolean;
  isAdmin?: boolean;
}) {
  const t = useTranslations("workspace.detail.chat");
  const { variant: mascotVariant } = useMascotPref();

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);
  const stickBottomRef = useRef(true);
  const [showJumpDown, setShowJumpDown] = useState(false);

  // Tracks the scrolling on the phone to toggle the jump button.
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

  useEffect(() => {
    if (isFirstRender.current && messages.length > 0) {
      const c = scrollContainerRef.current;
      if (c) c.scrollTop = c.scrollHeight;
      isFirstRender.current = false;
    }
  }, [messages.length]);

  // Follows the stream only while you are at the bottom.
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickBottomRef.current = distance < 50;
      // The button only appears from four screen heights of backlog on.
      setShowJumpDown(distance > el.clientHeight * 4);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    if (stickBottomRef.current) {
      el.scrollTop = el.scrollHeight;
      setShowJumpDown(false);
      return;
    }
    setShowJumpDown(el.scrollHeight - el.scrollTop - el.clientHeight > el.clientHeight * 4);
  }, [messages]);

  // Jumps to the end and resumes following along.
  function jumpDown() {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    stickBottomRef.current = true;
    setShowJumpDown(false);
  }

  // Stable callbacks via refs, otherwise the memoisation breaks.
  const sourcesRef = useRef(sources);
  sourcesRef.current = sources;
  const onPillClickRef = useRef(onPillClick);
  onPillClickRef.current = onPillClick;
  const onRetryRef = useRef(onRetry);
  onRetryRef.current = onRetry;

  const handleRetry = useCallback(() => onRetryRef.current?.(), []);

  const getFilename = useCallback(
    (srcUuid: string) => sourcesRef.current.find((s) => s.uuid === srcUuid)?.filename ?? srcUuid,
    [],
  );

  // Holds the scroll height so opening the viewer does not make the chat jump.
  const handleChipClick = useCallback(
    // Chips only jump, only a selection of your own is highlighted.
    (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean, endTime?: number, chunkStart?: number) => {
      const el = scrollContainerRef.current;
      const savedTop = el?.scrollTop ?? 0;
      // The transcript toggle does not belong to the chip.
      onPillClickRef.current(sourceUuid, page, filename, sourceText, startTime, isExact, undefined, endTime, chunkStart);
      if (el) {
        const restore = () => { el.scrollTop = savedTop; };
        requestAnimationFrame(() => { restore(); requestAnimationFrame(restore); });
        setTimeout(restore, 60);
      }
    },
    [],
  );

  return (
    <div data-tour="chat-panel" className="flex flex-col h-full">
      {pageScrollable && (
        <button
          type="button"
          onClick={jumpPage}
          aria-label={pageNearTop ? t("scrollToBottom") : t("scrollToTop")}
          className="show-on-short fixed right-3 bottom-3 z-50 w-10 h-10 items-center justify-center rounded-full shadow-lg"
          style={{ backgroundColor: "var(--kb)", color: "white" }}
        >
          {pageNearTop ? <CaretDown size={18} weight="bold" /> : <CaretUp size={18} weight="bold" />}
        </button>
      )}
      {/* Mobil bleibt die Kopfzeile als schmale Zeile stehen, sonst gaebe es
          keinen Weg mehr zu "Chatprotokoll loeschen". */}
      <ChatHeader
        messageCount={messages.length}
        onClear={onClear}
        onMinimize={onMinimize}
        compact={hideHeader}
      />

      {/* Messages */}
      <div className="relative flex-1 min-h-0 flex flex-col">
      {/* Ohne Scroll-Anchoring bleibt der Rollstand stehen, wenn eine aufgeklappte Stelle
          Platz braucht: der Text darunter rueckt nach, statt dass der obere Teil hochspringt. */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto" style={{ overflowAnchor: "none" }}>
        <div data-testid="chat-messages" className="mx-auto w-full p-3 flex flex-col gap-5" style={{ maxWidth: 920 }}>
          {messages.length === 0 && !loading && (
            <ChatEmptyState
              activeSourceIds={activeSourceIds}
              onSendPrompt={onSendPrompt}
              variant={mascotVariant}
            />
          )}

          {(() => {
            const recentAssistantIdx = new Set(
              messages
                .map((m, idx) => (m.role === "assistant" ? idx : -1))
                .filter((idx) => idx >= 0)
                .slice(-2)
            );
            return messages.map((msg, i) => (
              <ChatMessage
                key={msg.id ?? i}
                msg={msg}
                msgKey={String(msg.id ?? i)}
                activeSourceIds={activeSourceIds}
                getFilename={getFilename}
                onChipClick={handleChipClick}
                onSaveNote={onSaveNote}
                onRetry={onRetry ? handleRetry : undefined}
                loading={loading}
                variant={mascotVariant}
                isLatest={i === messages.length - 1}
                collapseByDefault={msg.role === "assistant" && !recentAssistantIdx.has(i)}
                popupActions={popupActions}
                isAdmin={isAdmin}
              />
            ));
          })()}
        </div>
      </div>

      {showJumpDown && (
        <IconButton
          onClick={jumpDown}
          aria-label={t("scrollToBottom")}
          title={t("scrollToBottom")}
          data-testid="chat-jump-down"
          className="hide-on-short absolute bottom-3 right-4 z-20 shadow-md"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", color: "var(--muted)" }}
        >
          <CaretDown size={14} weight="bold" />
        </IconButton>
      )}
      </div>

      <ChatInputBar
        loading={loading}
        activeSourceIds={activeSourceIds}
        onSend={onSend}
        onStop={onStop}
        externalTextareaRef={externalTextareaRef}
        registerSetInput={registerSetInput}
      />
      <p className="hide-on-short w-full text-center mt-1 pb-0 text-xs" style={{ color: "var(--muted)" }}>
        {t("aiNotice")}
      </p>
    </div>
  );
}
