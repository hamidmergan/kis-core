"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi } from "@/lib/api";
import type { CampusNachricht } from "../_types";

interface Options {
  chatId: number | null;
  /** Called when the backend opened a new chat for the first question. */
  onChatCreated: (chatId: number, title: string) => void;
  /** Called after every finished answer, so the list can move the chat up. */
  onAnswered: (chatId: number) => void;
}

interface MessagesPayload {
  id: number;
  title: string;
  question_count: number;
  messages: (CampusNachricht & { id: number })[];
}

const INACTIVITY_MS = 90_000;

export function useCampusChat({ chatId, onChatCreated, onAnswered }: Options) {
  const t = useTranslations("tools.campus");
  const [messages, setMessages] = useState<CampusNachricht[]>([]);
  const [loading, setLoading] = useState(false);
  const [chatFull, setChatFull] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  // The chat the running stream just opened, so switching to it must not abort or reload.
  const createdRef = useRef<number | null>(null);

  useEffect(() => {
    if (chatId !== null && createdRef.current === chatId) {
      createdRef.current = null;
      return;
    }
    abortRef.current?.abort();
    setChatFull(false);
    if (chatId === null) {
      setMessages([]);
      setQuestionCount(0);
      return;
    }
    let cancelled = false;
    backendApi
      .getJson<MessagesPayload>(`/campus/chats/${chatId}/messages`)
      .then((data) => {
        if (cancelled) return;
        setMessages(data.messages.map((m) => ({ ...m, sources: m.sources ?? [], places: m.places ?? [] })));
        setQuestionCount(data.question_count);
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [chatId]);

  const updateLast = useCallback((patch: Partial<CampusNachricht>) => {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last) updated[updated.length - 1] = { ...last, ...patch };
      return updated;
    });
  }, []);

  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || loading) return;
      setLoading(true);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text, sources: [], places: [] },
        { role: "assistant", content: "", sources: [], places: [], streaming: true },
      ]);
      const ac = new AbortController();
      abortRef.current = ac;
      let timer: ReturnType<typeof setTimeout> | null = null;
      let timedOut = false;
      const resetTimer = () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          timedOut = true;
          ac.abort();
        }, INACTIVITY_MS);
      };
      let answeredChat: number | null = null;
      try {
        resetTimer();
        const res = await fetch("/api/campus-stream", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          signal: ac.signal,
          body: JSON.stringify({ question: text, ...(chatId !== null && { chat_id: chatId }) }),
        });
        if (res.ok && res.body) {
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          let pending = "";
          let raf: number | null = null;
          const flush = () => {
            if (!pending) return;
            const chunk = pending;
            pending = "";
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last) updated[updated.length - 1] = { ...last, content: last.content + chunk };
              return updated;
            });
          };
          const handle = (line: string) => {
            if (!line.startsWith("data: ")) return;
            try {
              const evt = JSON.parse(line.slice(6));
              if (evt.token) {
                pending += evt.token;
                if (raf == null) raf = requestAnimationFrame(() => { flush(); raf = null; });
              } else if (evt.meta) {
                answeredChat = evt.meta.chat_id;
                updateLast({ metaArrived: true });
                if (chatId === null) {
                  createdRef.current = evt.meta.chat_id;
                  onChatCreated(evt.meta.chat_id, evt.meta.title);
                }
              } else if (evt.done) {
                if (raf != null) { cancelAnimationFrame(raf); raf = null; }
                flush();
                updateLast({
                  id: evt.message_id,
                  content: evt.answer,
                  sources: evt.sources ?? [],
                  places: evt.places ?? [],
                  no_source: !!evt.no_source,
                  streaming: false,
                });
                setQuestionCount((n) => n + 1);
              } else if (evt.error) {
                const key = evt.code === "upstream_busy" ? "upstreamBusy" : "genericError";
                updateLast({ content: t(key), failed: true, streaming: false });
              }
            } catch {
              // A broken line is skipped, the next one still counts.
            }
          };
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            resetTimer();
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";
            for (const line of lines) handle(line);
          }
          if (buffer.trim()) handle(buffer);
          if (raf != null) { cancelAnimationFrame(raf); raf = null; }
          flush();
        } else if (res.status === 409) {
          setChatFull(true);
          updateLast({ content: t("chatFull"), failed: true, streaming: false });
        } else if (res.status === 429) {
          let msg = t("tooManyRequests");
          try {
            const err = await res.json();
            if (err?.detail?.message) msg = err.detail.message;
          } catch {
            // The generic text stays.
          }
          updateLast({ content: msg, failed: true, streaming: false });
        } else {
          updateLast({ content: t("genericError"), failed: true, streaming: false });
        }
      } catch {
        if (timedOut) updateLast({ content: t("genericError"), failed: true, streaming: false });
        else updateLast({ streaming: false });
      } finally {
        if (timer) clearTimeout(timer);
        abortRef.current = null;
        setLoading(false);
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.streaming) updated[updated.length - 1] = { ...last, streaming: false };
          return updated;
        });
        if (answeredChat !== null) onAnswered(answeredChat);
      }
    },
    [chatId, loading, onAnswered, onChatCreated, t, updateLast],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const rate = useCallback(async (messageId: number, value: number) => {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback: value } : m)));
    try {
      await backendApi.postJson(`/campus/messages/${messageId}/feedback`, { value });
    } catch {
      // The thumb stays as clicked, the next load shows the stored value.
    }
  }, []);

  return { messages, loading, chatFull, questionCount, send, stop, rate };
}
