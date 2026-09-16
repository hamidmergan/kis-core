"use client";

import { useCallback } from "react";
import { _isMediaFile, _youtubeIdOf } from "../_utils";
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

  // An opened source does not narrow the selection, it used to stick when stored.
  const openViewer = useCallback((source: Source, page = 1, highlightText?: string, exactSelection?: boolean, isCitation = false) => {
    setViewerSource({ uuid: source.uuid, filename: source.filename, page, highlightText, exactSelection, isCitation, nonce: Date.now(), youtubeId: _youtubeIdOf(source) });
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
      // setInput has to come after the switch, on the phone the input hangs on nothing otherwise.
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

  // sourceText is verbatim text to highlight when isExact, otherwise the claim the chip backs.
  const pillClick = useCallback((sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean, hideTranscript?: boolean, endTime?: number, chunkStart?: number) => {
    const src = sources.find((s) => s.uuid === sourceUuid);
    const isMedia = _isMediaFile(filename);
    if (isMedia) {
      // isCitation marks the jump of a citation chip, sourceText is the claim and no search term.
      setViewerSource({ uuid: sourceUuid, filename, page: 0, startTime, endTime, chunkStart, citationClaim: sourceText, isCitation: true, hideTranscript, nonce: Date.now(), youtubeId: src ? _youtubeIdOf(src) : undefined });
      setPanels((prev) => ({ ...prev, quellen: true }));
      if (isMobile) setActiveTab("quellen");
      return;
    }
    setViewerSource({
      uuid: sourceUuid, filename, page,
      highlightText: isExact ? sourceText : undefined,
      exactSelection: isExact,
      citationClaim: isExact ? undefined : sourceText,
      isCitation: true, nonce: Date.now(), youtubeId: src ? _youtubeIdOf(src) : undefined,
    });
    setPanels((prev) => ({ ...prev, quellen: true }));
    if (isMobile) setActiveTab("quellen");
  }, [sources, setViewerSource, setPanels, isMobile, setActiveTab]);

  return {
    openViewer,
    closeViewer,
    askWithSelection,
    askChat,
    customQuestion,
    pillClick,
  };
}
