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
  onPillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean, hideTranscript?: boolean, endTime?: number) => void;
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
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
      stickBottomRef.current = atBottom;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el || !stickBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Stable callback identities via refs - otherwise React.memo on ChatMessage
  // gets invalidated on every re-render of page.tsx (e.g. tab switch), because
  // `onPillClick` has deps like `activeTab` and its identity keeps changing.
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

  // Wrap onPillClick so opening the viewer doesn't cause the chat to jump.
  // Captures scrollTop before the click and restores it across a few frames
  // while the panel layout settles.
  const handleChipClick = useCallback(
    // Chips are nav-only: a click scrolls to the page/timestamp. Only a popup/action-
    // bar exact selection (isExact + sourceText) carries text to highlight.
    (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean, endTime?: number) => {
      const el = scrollContainerRef.current;
      const savedTop = el?.scrollTop ?? 0;
      // hideTranscript stays undefined here: that flag belongs to the listening exercise,
      // never to a chip. endTime is the last argument of pillClick.
      onPillClickRef.current(sourceUuid, page, filename, sourceText, startTime, isExact, undefined, endTime);
      if (el) {
        const restore = () => { el.scrollTop = savedTop; };
        requestAnimationFrame(() => { restore(); requestAnimationFrame(restore); });
        setTimeout(restore, 60);
      }
    },
    [],
  );

  return (
    <div className="flex flex-col h-full chat-60vh">
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
      {!hideHeader && (
        <ChatHeader
          messageCount={messages.length}
          onClear={onClear}
          onMinimize={onMinimize}
        />
      )}

      {/* Messages */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
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
      <p className="hide-on-short w-full text-center mt-0 pb-0 text-xs" style={{ color: "var(--muted)" }}>
        {t("feedbackQuestion")}{" "}
        <a href="mailto:hamid.mergan@th-luebeck.de" className="hover:underline hover:text-[var(--kb)] transition-colors">
          hamid.mergan@th-luebeck.de
        </a>
      </p>
    </div>
  );
}
