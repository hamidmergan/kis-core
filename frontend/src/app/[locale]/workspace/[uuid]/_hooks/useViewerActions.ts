"use client";

import { useCallback } from "react";
import { _isMediaFile } from "../_utils";
import type { PanelKey, Source, ViewerState } from "../_types";

interface UseViewerActionsOptions {
  sources: Source[];
  setViewerSource: (v: ViewerState | null) => void;
  setPanels: React.Dispatch<React.SetStateAction<Record<PanelKey, boolean>>>;
  panels: Record<PanelKey, boolean>;
  isMobile: boolean;
  activeTab: PanelKey;
  setActiveTab: (k: PanelKey) => void;
  chatSetInputRef: React.MutableRefObject<((v: string) => void) | null>;
  chatTextareaRef: React.RefObject<HTMLTextAreaElement | null>;
  sendChatMessage: (text: string, directText?: boolean, sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string; actionKey?: string }) => void;
}

export function useViewerActions(opts: UseViewerActionsOptions) {
  const {
    sources,
    setViewerSource, setPanels, panels,
    isMobile, activeTab, setActiveTab,
    chatSetInputRef, chatTextareaRef, sendChatMessage,
  } = opts;

  // Opening a source does NOT narrow selectedSourceIds. The chat already scopes
  // to the viewer source via `viewerSource ? [viewerSource.uuid] : selectedSourceIds`
  // (see useChat). Narrowing here only overwrote — and persisted to sessionStorage —
  // the user's multi-source selection, which then came back as a stuck single
  // source after navigating away/reloading with the viewer still open.
  const openViewer = useCallback((source: Source, page = 1, highlightText?: string, exactSelection?: boolean, isCitation = false) => {
    setViewerSource({ uuid: source.uuid, filename: source.filename, page, highlightText, exactSelection, isCitation, nonce: Date.now() });
    setPanels((prev) => ({ ...prev, quellen: true }));
    if (isMobile) setActiveTab("quellen");
  }, [setViewerSource, setPanels, isMobile, setActiveTab]);

  const closeViewer = useCallback(() => {
    setViewerSource(null);
  }, [setViewerSource]);

  const askWithSelection = useCallback((prompt: string, sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string; actionKey?: string }) => {
    if (isMobile) setActiveTab("chat");
    else setPanels((prev) => ({ ...prev, chat: true }));
    sendChatMessage(prompt, true, sourceInfo);
  }, [isMobile, setActiveTab, setPanels, sendChatMessage]);

  // Fill chat input and focus it. `switchTab` forces mobile-tab switch to chat.
  const fillChatInput = useCallback((value: string, wasOpen: boolean, switchTab: boolean) => {
    if (isMobile || switchTab) setActiveTab("chat");
    else setPanels((prev) => ({ ...prev, chat: true }));
    const delay = wasOpen ? 50 : 300;
    setTimeout(() => {
      // setInput must come AFTER the tab/panel switch: on smartphone the
      // ChatInputBar is unmounted while the sources/studio tab is active, so
      // chatSetInputRef is null. The mount cycle is only complete after the setTimeout delay.
      chatSetInputRef.current?.(value);
      const el = chatTextareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(value.length, value.length);
      el.scrollTop = el.scrollHeight;
    }, delay);
  }, [isMobile, setActiveTab, setPanels, chatSetInputRef, chatTextareaRef]);

  const askChat = useCallback((text: string, switchTab = false) => {
    const chatWasOpen = isMobile ? activeTab === "chat" : panels.chat;
    fillChatInput(text + "\n\n", chatWasOpen, switchTab);
  }, [isMobile, activeTab, panels.chat, fillChatInput]);

  const customQuestion = useCallback((selectedText: string) => {
    const chatWasOpen = isMobile ? activeTab === "chat" : panels.chat;
    fillChatInput(`"${selectedText}"\n\n`, chatWasOpen, false);
  }, [isMobile, activeTab, panels.chat, fillChatInput]);

  const pillClick = useCallback((sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => {
    const src = sources.find((s) => s.uuid === sourceUuid);
    const isMedia = _isMediaFile(filename);
    if (isMedia) {
      // isCitation marks this as a citation-chip jump so the transcript pins the cited
      // segment + shows its jump/dismiss bar, mirroring the PDF page-frame behaviour.
      setViewerSource({ uuid: sourceUuid, filename, page: 0, startTime, isCitation: true, nonce: Date.now() });
      setPanels((prev) => ({ ...prev, quellen: true }));
      if (isMobile) setActiveTab("quellen");
      return;
    }
    if (src) {
      openViewer(src, page, sourceText, isExact, true);
      return;
    }
    setViewerSource({ uuid: sourceUuid, filename, page, highlightText: sourceText, exactSelection: isExact, isCitation: true, nonce: Date.now() });
    setPanels((prev) => ({ ...prev, quellen: true }));
    if (isMobile) setActiveTab("quellen");
  }, [sources, setViewerSource, setPanels, isMobile, setActiveTab, openViewer]);

  return {
    openViewer,
    closeViewer,
    askWithSelection,
    askChat,
    customQuestion,
    pillClick,
  };
}
