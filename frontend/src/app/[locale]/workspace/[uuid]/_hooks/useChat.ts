"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { ChatMessage, ViewerState } from "../_types";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { api } from "@/lib/api";
import { popupActionsUrl } from "./_popupActionsUrl";

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
  chatLang: "de" | "en";
  popupTranslateLang: string;
}

export function useChat({ uuid, enrollmentId, selectedSourceIds, viewerSource, chatLang, popupTranslateLang }: UseChatOptions) {
  void chatLang; // popup labels now follow UI locale (Accept-Language); chatLang stays in the API for callers
  void viewerSource; // the open source no longer scopes the chat, see sendChatMessage
  const labels = useWorkspaceLabel();
  const tChat = useTranslations("workspace.detail.chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [popupActions, setPopupActions] = useState<PopupAction[]>([]);

  const chatTextareaRef = useRef<HTMLTextAreaElement>(null);
  const chatSetInputRef = useRef<((v: string) => void) | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stopChat = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  // Aborts the stream when the panel is left.
  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
  }, []);

  const registerChatSetInput = useCallback((setter: ((v: string) => void) | null) => {
    chatSetInputRef.current = setter;
  }, []);

  const loadMessages = useCallback(async () => {
    try {
      const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : "";
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/messages${eidParam}`, { credentials: "include" });
      if (res.ok) {
        const raw: ChatMessage[] = await res.json();
        const hydrated = raw.map((m) => {
          const popup = m.source_pages?.find((s) => s.is_popup_selection);
          if (!popup || m.popup_selection) return m;
          return {
            ...m,
            popup_selection: {
              uuid: popup.source_uuid,
              page: popup.page_number,
              text: popup.source_text ?? "",
              ...(popup.action_key && { action_key: popup.action_key }),
              ...(popup.action_icon && { action_icon: popup.action_icon }),
            },
          };
        });
        setMessages(hydrated);
      }
    } catch { /* ignore */ }
  }, [uuid, enrollmentId]);

  const loadPopupActions = useCallback(async () => {
    try {
      // The target language travels as a parameter and reloads on a change.
      const res = await api.fetch(popupActionsUrl(popupTranslateLang));
      if (res.ok) {
        const d = await res.json();
        setPopupActions(d.actions ?? []);
      }
    } catch { /* ignore */ }
  }, [popupTranslateLang]);

  const sendChatMessage = useCallback(async (
    content: string,
    directText = false,
    sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string; actionKey?: string }
  ) => {
    content = content.replace(/\s*\[(?:Q\d+,\s*)?S\.\s*\d+\]/g, "");
    // An opened source does not narrow the selection.
    const effectiveSourceIds = selectedSourceIds;
    if (!content.trim()) return;
    if (!directText && effectiveSourceIds.length === 0) return;
    const msgSourceCount = directText ? 1 : effectiveSourceIds.length;
    const actionDef = sourceInfo?.actionKey
      ? popupActions.find((a) => a.key === sourceInfo.actionKey)
      : undefined;
    const popupSel = sourceInfo?.selectedText
      ? {
          uuid: sourceInfo.uuid,
          page: sourceInfo.page,
          text: sourceInfo.selectedText,
          ...(sourceInfo.actionKey && { action_key: sourceInfo.actionKey }),
          ...(actionDef?.icon && { action_icon: actionDef.icon }),
        }
      : undefined;
    setMessages((prev) => [...prev, { role: "user", content: content.trim(), sourceCount: msgSourceCount, popup_selection: popupSel }]);
    setChatLoading(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "", sourceCount: msgSourceCount, popup_selection: popupSel }]);

    // A net against an answer that stayed empty, otherwise the display types forever.
    const failIfEmpty = () =>
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant" || last.content || last.aborted) return prev;
        const updated = [...prev];
        updated[updated.length - 1] = { ...last, content: tChat("genericError"), failed: true };
        return updated;
      });

    const updateLast = (patch: Partial<ChatMessage>) =>
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last) updated[updated.length - 1] = { ...last, ...patch };
        return updated;
      });

    const ac = new AbortController();
    abortControllerRef.current = ac;
    // If nothing comes for a long time, the connection counts as dead.
    const INACTIVITY_MS = 90_000;
    let inactivityTimer: ReturnType<typeof setTimeout> | null = null;
    let timedOut = false;
    const resetInactivity = () => {
      if (inactivityTimer) clearTimeout(inactivityTimer);
      inactivityTimer = setTimeout(() => { timedOut = true; ac.abort(); }, INACTIVITY_MS);
    };
    const clearInactivity = () => {
      if (inactivityTimer) { clearTimeout(inactivityTimer); inactivityTimer = null; }
    };

    try {
      resetInactivity();
      const res = await fetch(`/api/ai-assistant-stream/${uuid}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        signal: ac.signal,
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
            ...(sourceInfo.actionKey && { action_key: sourceInfo.actionKey }),
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
              // Details before the stream so chips resolve while it is still running.
              updateLast({
                source_qmap: evt.qmap,
                source_pages: evt.source_pages,
                applied_level: evt.applied_level ?? null,
              });
            } else if (evt.done) {
              if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
              flushTokens();
              const patch: Record<string, unknown> = { source_pages: evt.source_pages, source_qmap: evt.source_qmap };
              if (evt.answer) patch.content = evt.answer;
              updateLast(patch);
            } else if (evt.error) {
              // With an overloaded provider it now says 'try again later'.
              const key = evt.code === "upstream_busy" ? "upstreamBusy" : "genericError";
              updateLast({ content: tChat(key), failed: true });
            }
          } catch { /* skip malformed */ }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          resetInactivity();
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) processLine(line);
        }
        if (buffer.trim()) processLine(buffer);
        if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
        clearInactivity();
        flushTokens();
      } else if (res.status === 409) {
        updateLast({ content: tChat("indexingInProgress", { label: labels.singular }) });
      } else if (res.status === 429) {
        // The block names the concrete time.
        let msg = tChat("tooManyRequests");
        try {
          const err = await res.json();
          if (err?.detail?.message) msg = err.detail.message;
        } catch { /* ignore */ }
        updateLast({ content: msg });
      } else {
        // Blocks stay without a retry button, it would hit the same block.
        updateLast({ content: tChat("genericError"), failed: true });
      }
    } catch {
      // A cancellation keeps the partial text, a timeout reports as an error.
      if (timedOut) {
        updateLast({ content: tChat("genericError"), failed: true });
      } else if (ac.signal.aborted) {
        updateLast({ aborted: true });
      } else {
        updateLast({ content: tChat("genericError"), failed: true });
      }
    } finally {
      clearInactivity();
      if (abortControllerRef.current === ac) abortControllerRef.current = null;
      failIfEmpty();
      setChatLoading(false);
    }
  }, [uuid, enrollmentId, selectedSourceIds, popupActions]);

  // Read through a ref so the callback stays stable.
  const messagesRef = useRef<ChatMessage[]>(messages);
  messagesRef.current = messages;

  /** Asks the last question again, the failed bubble stays. */
  const retryLast = useCallback(() => {
    if (chatLoading) return;
    const lastUser = [...messagesRef.current].reverse().find((m) => m.role === "user");
    if (!lastUser || lastUser.popup_selection) return;
    sendChatMessage(lastUser.content);
  }, [chatLoading, sendChatMessage]);

  useEffect(() => {
    loadPopupActions();
  }, [loadPopupActions]);

  return {
    messages, setMessages,
    chatLoading,
    popupActions, setPopupActions,
    chatTextareaRef, chatSetInputRef,
    registerChatSetInput,
    loadMessages, sendChatMessage, stopChat, retryLast,
  };
}
