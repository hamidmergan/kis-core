"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, ViewerState } from "../_types";

interface PopupAction {
  key: string;
  label: string;
  icon: string;
  prompt: string;
  min_words: number;
}

interface UseChatOptions {
  uuid: string;
  enrollmentId: number | null;
  selectedSourceIds: string[];
  viewerSource: ViewerState | null;
}

export function useChat({ uuid, enrollmentId, selectedSourceIds, viewerSource }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [popupActions, setPopupActions] = useState<PopupAction[]>([]);

  const chatTextareaRef = useRef<HTMLTextAreaElement>(null);
  const chatSetInputRef = useRef<((v: string) => void) | null>(null);

  const registerChatSetInput = useCallback((setter: ((v: string) => void) | null) => {
    chatSetInputRef.current = setter;
  }, []);

  const loadMessages = useCallback(async () => {
    try {
      const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : "";
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/messages${eidParam}`, { credentials: "include" });
      if (res.ok) setMessages(await res.json());
    } catch { /* ignore */ }
  }, [uuid, enrollmentId]);

  const loadPopupActions = useCallback(async () => {
    try {
      const res = await fetch("/api/ai-assistant/popup-actions", { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        setPopupActions(d.actions ?? []);
      }
    } catch { /* ignore */ }
  }, []);

  const sendChatMessage = useCallback(async (
    content: string,
    directText = false,
    sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string }
  ) => {
    content = content.replace(/\s*\[(?:Q\d+,\s*)?S\.\s*\d+\]/g, "");
    const effectiveSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;
    if (!content.trim()) return;
    if (!directText && effectiveSourceIds.length === 0) return;
    const msgSourceCount = directText ? 1 : effectiveSourceIds.length;
    const popupSel = sourceInfo?.selectedText
      ? { uuid: sourceInfo.uuid, page: sourceInfo.page, text: sourceInfo.selectedText }
      : undefined;
    setMessages((prev) => [...prev, { role: "user", content: content.trim(), sourceCount: msgSourceCount, popup_selection: popupSel }]);
    setChatLoading(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "", sourceCount: msgSourceCount, popup_selection: popupSel }]);

    const updateLast = (patch: Partial<ChatMessage>) =>
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last) updated[updated.length - 1] = { ...last, ...patch };
        return updated;
      });

    try {
      const res = await fetch(`/api/ai-assistant-stream/${uuid}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: content.trim(),
          active_source_ids: directText ? [] : effectiveSourceIds,
          direct_text: directText,
          ...(enrollmentId && { enrollment_id: enrollmentId }),
          ...(sourceInfo && {
            source_uuid: sourceInfo.uuid,
            source_filename: sourceInfo.filename,
            source_page: sourceInfo.page,
            source_text: sourceInfo.selectedText,
          }),
        }),
      });
      if (res.ok && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let pendingTokens = "";
        let rafId: number | null = null;
        const flushTokens = () => {
          if (!pendingTokens) return;
          const chunk = pendingTokens;
          pendingTokens = "";
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last) updated[updated.length - 1] = { ...last, content: last.content + chunk };
            return updated;
          });
        };

        const processLine = (line: string) => {
          if (!line.startsWith("data: ")) return;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.token) {
              pendingTokens += evt.token;
              if (rafId == null) {
                rafId = requestAnimationFrame(() => { flushTokens(); rafId = null; });
              }
            } else if (evt.qmap) {
              // Pre-stream metadata: lets citation chips resolve to the right
              // source while tokens are still arriving.
              updateLast({ source_qmap: evt.qmap, source_pages: evt.source_pages });
            } else if (evt.done) {
              if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
              flushTokens();
              const patch: Record<string, unknown> = { source_pages: evt.source_pages, source_qmap: evt.source_qmap };
              if (evt.answer) patch.content = evt.answer;
              updateLast(patch);
            } else if (evt.error) {
              updateLast({ content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." });
            }
          } catch { /* skip malformed */ }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) processLine(line);
        }
        if (buffer.trim()) processLine(buffer);
        if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
        flushTokens();
      } else if (res.status === 409) {
        updateLast({ content: "Der Workspace wird noch indiziert. Bitte warte einen Moment und versuche es erneut." });
      } else if (res.status === 429) {
        // Burst lock: too many chat requests in a short time. Backend returns
        // the concrete lock time in detail.message ("Chat ist bis HH:MM Uhr gesperrt").
        let msg = "Zu viele Anfragen. Bitte einen Moment warten und erneut senden.";
        try {
          const err = await res.json();
          if (err?.detail?.message) msg = err.detail.message;
        } catch { /* ignore */ }
        updateLast({ content: msg });
      } else {
        updateLast({ content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." });
      }
    } catch {
      updateLast({ content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." });
    } finally {
      setChatLoading(false);
    }
  }, [uuid, enrollmentId, selectedSourceIds, viewerSource]);

  useEffect(() => {
    loadPopupActions();
  }, [loadPopupActions]);

  return {
    messages, setMessages,
    chatLoading,
    popupActions, setPopupActions,
    chatTextareaRef, chatSetInputRef,
    registerChatSetInput,
    loadMessages, sendChatMessage,
  };
}
