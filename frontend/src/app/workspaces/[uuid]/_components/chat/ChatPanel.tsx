import React, { useCallback, useEffect, useRef, useState } from "react";
import { CaretDown, CaretUp } from "@phosphor-icons/react";
import type { ChatMessage as ChatMessageType, Source } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { ChatHeader } from "./ChatHeader";
import { ChatEmptyState } from "./ChatEmptyState";
import { ChatMessage } from "./ChatMessage";
import { ChatInputBar } from "./ChatInputBar";


export function ChatPanel({
  messages,
  activeSourceIds,
  sources,
  loading,
  onSend,
  onPillClick,
  onClear,
  externalTextareaRef,
  onSaveNote,
  onMinimize,
  onSendPrompt,
  registerSetInput,
  hideHeader,
}: {
  messages: ChatMessageType[];
  activeSourceIds: string[];
  sources: Source[];
  loading: boolean;
  onSend: (value: string) => void;
  onPillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
  moduleReady: boolean;
  onClear: () => void;
  externalTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  onMinimize?: () => void;
  onSendPrompt?: (text: string) => void;
  registerSetInput?: (setter: ((v: string) => void) | null) => void;
  hideHeader?: boolean;
}) {
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

  // Stabile Callback-Identitäten via Refs — sonst invalidiert React.memo auf
  // ChatMessage bei jedem Re-Render von page.tsx (z.B. Tab-Switch), weil
  // `onPillClick` Deps wie `activeTab` hat und die Identität dauernd wechselt.
  const sourcesRef = useRef(sources);
  sourcesRef.current = sources;
  const onPillClickRef = useRef(onPillClick);
  onPillClickRef.current = onPillClick;

  const getFilename = useCallback(
    (srcUuid: string) => sourcesRef.current.find((s) => s.uuid === srcUuid)?.filename ?? srcUuid,
    [],
  );

  // Wrap onPillClick so opening the viewer doesn't cause the chat to jump.
  // Captures scrollTop before the click and restores it across a few frames
  // while the panel layout settles.
  const handleChipClick = useCallback(
    (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => {
      const el = scrollContainerRef.current;
      const savedTop = el?.scrollTop ?? 0;
      onPillClickRef.current(sourceUuid, page, filename, sourceText, startTime, isExact);
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
          aria-label={pageNearTop ? "Nach unten scrollen" : "Nach oben scrollen"}
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
        <div className="mx-auto w-full p-3 flex flex-col gap-5" style={{ maxWidth: 720 }}>
          {messages.length === 0 && !loading && (
            <ChatEmptyState activeSourceIds={activeSourceIds} onSendPrompt={onSendPrompt} />
          )}

          {messages.map((msg, i) => (
            <ChatMessage
              key={msg.id ?? i}
              msg={msg}
              activeSourceIds={activeSourceIds}
              getFilename={getFilename}
              onChipClick={handleChipClick}
              onSaveNote={onSaveNote}
              loading={loading}
            />
          ))}
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
