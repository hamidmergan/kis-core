"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  toTranscript,
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

/**
 * Drives the CEFR diagnosis chat.
 *
 * The transcript is the whole state: it is posted back to the backend on every
 * turn and mirrored into localStorage, so a reload lands the learner back where
 * they left off instead of restarting the interview.
 */
export function useLanguageDiagnosis(
  userId: number | null | undefined,
  workspaceUuid: string,
) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [status, setStatus] = useState<Status>("loading");
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // The transcript the next request must send. Kept in a ref so `send` never
  // captures a stale copy and the kickoff effect can run exactly once.
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
          body: JSON.stringify({
            workspace_uuid: workspaceUuid,
            history: toTranscript(history),
          }),
        });
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(errBody.detail || `HTTP ${res.status}`);
        }
        const data = (await res.json()) as DiagnosisTurnResponse;
        // The reaction rides along on the same turn. The verdict has none: it is
        // rendered by the result screen, which has no bubble for it.
        const reaction = data.done ? undefined : data.reaction?.trim();
        const next: ChatTurn[] = [
          ...history,
          { role: "assistant", content: data.message, ...(reaction ? { reaction } : {}) },
        ];
        turnsRef.current = next;
        setTurns(next);

        if (data.done) {
          setResult({
            level: data.level,
            message: data.message,
            skill_scores: data.skill_scores,
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
    [userId, workspaceUuid],
  );

  // Kickoff: resume a saved transcript, or ask for the opening question.
  useEffect(() => {
    if (startedRef.current || !workspaceUuid) return;
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
  }, [userId, workspaceUuid, requestTurn]);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || status !== "answering") return;
      const withAnswer: ChatTurn[] = [...turnsRef.current, { role: "user", content: trimmed }];
      turnsRef.current = withAnswer;
      setTurns(withAnswer);
      // The draft is only written once the next question arrives, so a saved
      // transcript always ends on an assistant turn. A failed turn therefore
      // resumes at the last question rather than at a dangling answer.
      void requestTurn(withAnswer);
    },
    [status, userId, requestTurn],
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

  return { turns, status, result, errorMessage, send, retry, abort };
}
