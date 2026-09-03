"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { genericErrorMessage, parseDetail } from "@/lib/api";
import {
  toTranscript,
  DIAGNOSIS_ANSWER_MAX_CHARS,
  DIAGNOSIS_QUESTION_COUNT,
  type ChatTurn,
  type DiagnosisResult,
  type DiagnosisTurnResponse,
} from "../_components/language_training/_diagnosis_types";

type Status = "loading" | "answering" | "done" | "error";

function storageKey(userId: number | null | undefined) {
  return userId ? `kis-diagnosis-chat-${userId}` : null;
}

function loadDraft(userId: number | null | undefined): ChatTurn[] | null {
  const key = storageKey(userId);
  if (!key || typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0 ? (parsed as ChatTurn[]) : null;
  } catch {
    return null;
  }
}

function saveDraft(userId: number | null | undefined, turns: ChatTurn[]) {
  const key = storageKey(userId);
  if (!key || typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(turns));
  } catch {
    /* ignore quota errors */
  }
}

function clearDraft(userId: number | null | undefined) {
  const key = storageKey(userId);
  if (!key || typeof window === "undefined") return;
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/** The history is the whole state and survives a reload. */
export function useLanguageDiagnosis(userId: number | null | undefined) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [status, setStatus] = useState<Status>("loading");
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Question count and answer length come from the server, the constants are a fallback.
  const [questionCount, setQuestionCount] = useState(DIAGNOSIS_QUESTION_COUNT);
  const [answerMaxChars, setAnswerMaxChars] = useState(DIAGNOSIS_ANSWER_MAX_CHARS);
  useEffect(() => {
    fetch("/api/ai-assistant/language-diagnosis/config", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        if (typeof d.question_count === "number") setQuestionCount(d.question_count);
        if (typeof d.answer_max_chars === "number") setAnswerMaxChars(d.answer_max_chars);
      })
      .catch(() => { /* keep fallbacks */ });
  }, []);

  // As a ref so no stale history is sent along.
  const turnsRef = useRef<ChatTurn[]>([]);
  const startedRef = useRef(false);

  const requestTurn = useCallback(
    async (history: ChatTurn[]) => {
      setStatus("loading");
      setErrorMessage(null);
      try {
        const res = await fetch("/api/ai-assistant/language-diagnosis/turn", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ history: toTranscript(history) }),
        });
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(parseDetail(errBody.detail, genericErrorMessage()));
        }
        const data = (await res.json()) as DiagnosisTurnResponse;
        // A running turn is one question, the verdict carries none of these fields.
        const next: ChatTurn[] = [
          ...history,
          data.done
            ? { role: "assistant", content: data.message }
            : {
                role: "assistant",
                content: data.message,
                ...(data.options ? { options: data.options } : {}),
                ...(data.multi ? { multi: data.multi } : {}),
                ...(data.short ? { short: data.short } : {}),
              },
        ];
        turnsRef.current = next;
        setTurns(next);

        if (data.done) {
          setResult({
            level: data.level,
            message: data.message,
          });
          setStatus("done");
          clearDraft(userId);
        } else {
          saveDraft(userId, next);
          setStatus("answering");
        }
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
        setStatus("error");
      }
    },
    [userId],
  );

  // Kickoff: resume a saved transcript, or ask for the opening question.
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    const draft = loadDraft(userId);
    if (draft) {
      turnsRef.current = draft;
      setTurns(draft);
      // A draft always ends on an assistant question, so the learner answers next.
      setStatus("answering");
      return;
    }
    void requestTurn([]);
  }, [userId, requestTurn]);

  const send = useCallback(
    (text: string, selected?: string[]) => {
      if (status !== "answering") return;
      // An empty answer is a deliberate skip and counts as not coped with.
      const trimmed = text.trim();
      const answer: ChatTurn = {
        role: "user",
        content: trimmed,
        // Clicked options ride along in selected, free text has none.
        ...(selected && selected.length ? { selected } : {}),
      };
      const withAnswer: ChatTurn[] = [...turnsRef.current, answer];
      turnsRef.current = withAnswer;
      setTurns(withAnswer);
      // The draft is only written with the next question, an abort resumes at the last one.
      void requestTurn(withAnswer);
    },
    [status, requestTurn],
  );

  /** Re-send the last request after a failure, without losing the transcript. */
  const retry = useCallback(() => {
    void requestTurn(turnsRef.current);
  }, [requestTurn]);

  /** Throw the transcript away, so a later restart begins a fresh interview. */
  const abort = useCallback(() => {
    clearDraft(userId);
    turnsRef.current = [];
    setTurns([]);
    setResult(null);
    setErrorMessage(null);
  }, [userId]);

  return { turns, status, result, errorMessage, send, retry, abort, questionCount, answerMaxChars };
}
