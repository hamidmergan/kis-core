"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { ChatMessage, ViewerState } from "../_types";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { api } from "@/lib/api";

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
}

export function useChat({ uuid, enrollmentId, selectedSourceIds, viewerSource, chatLang }: UseChatOptions) {
  void chatLang; // popup labels now follow UI locale (Accept-Language); chatLang stays in the API for callers
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
      // Locale comes from Accept-Language (api.fetch reads NEXT_LOCALE cookie),
      // not chat_lang - popup labels are UI strings, not LLM output language.
      const res = await api.fetch("/api/ai-assistant/popup-actions");
      if (res.ok) {
        const d = await res.json();
        setPopupActions(d.actions ?? []);
      }
    } catch { /* ignore */ }
  }, []);

  const sendChatMessage = useCallback(async (
    content: string,
    directText = false,
    sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string; actionKey?: string }
  ) => {
    content = content.replace(/\s*\[(?:Q\d+,\s*)?S\.\s*\d+\]/g, "");
    const effectiveSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;
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

    const updateLast = (patch: Partial<ChatMessage>) =>
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last) updated[updated.length - 1] = { ...last, ...patch };
        return updated;
      });

    const ac = new AbortController();
    abortControllerRef.current = ac;
    // Inactivity safety net: if no chunk arrives for this long, the connection
    // is presumed dead (network zombie, provider stall the backend missed) and
    // we bail so the user can retry instead of staring at a frozen indicator.
    // Backend has its own 60s inactivity timeout, so this is a slightly looser
    // outer bound that only fires when the backend itself is unreachable.
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
              // Pre-stream metadata: lets citation chips resolve to the right
              // source while tokens are still arriving.
              updateLast({ source_qmap: evt.qmap, source_pages: evt.source_pages });
            } else if (evt.line_done) {
              const { index, text } = evt.line_done as { index: number; text: string };
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last) {
                  const gl = last.groundedLines ? [...last.groundedLines] : [];
                  gl[index] = text;
                  updated[updated.length - 1] = { ...last, groundedLines: gl };
                }
                return updated;
              });
            } else if (evt.done) {
              if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
              flushTokens();
              const patch: Record<string, unknown> = { source_pages: evt.source_pages, source_qmap: evt.source_qmap };
              if (evt.answer) patch.content = evt.answer;
              patch.groundedLines = undefined;
              updateLast(patch);
            } else if (evt.error) {
              updateLast({ content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." });
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
        // Burst lock: too many chat requests in a short time. Backend returns
        // the concrete lock time in detail.message ("Chat ist bis HH:MM Uhr gesperrt").
        let msg = tChat("tooManyRequests");
        try {
          const err = await res.json();
          if (err?.detail?.message) msg = err.detail.message;
        } catch { /* ignore */ }
        updateLast({ content: msg });
      } else {
        updateLast({ content: tChat("genericError") });
      }
    } catch {
      // AbortController-triggered cancel: keep partial text + flag aborted.
      // Inactivity timeout also routes through abort but with timedOut=true so
      // the user sees an actionable error instead of a silent "you cancelled" flag.
      // Other errors (network drop, parse fail) overwrite with generic error text.
      if (timedOut) {
        updateLast({ content: tChat("genericError") });
      } else if (ac.signal.aborted) {
        updateLast({ aborted: true });
      } else {
        updateLast({ content: tChat("genericError") });
      }
    } finally {
      clearInactivity();
      if (abortControllerRef.current === ac) abortControllerRef.current = null;
      setChatLoading(false);
    }
  }, [uuid, enrollmentId, selectedSourceIds, viewerSource, popupActions]);

  useEffect(() => {
    loadPopupActions();
  }, [loadPopupActions]);

  return {
    messages, setMessages,
    chatLoading,
    popupActions, setPopupActions,
    chatTextareaRef, chatSetInputRef,
    registerChatSetInput,
    loadMessages, sendChatMessage, stopChat,
  };
}
