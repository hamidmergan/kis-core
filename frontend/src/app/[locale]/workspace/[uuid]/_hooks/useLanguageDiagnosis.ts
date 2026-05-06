"use client";

import { useCallback, useEffect, useState } from "react";
import {
  DIAGNOSIS_QUESTIONS,
  type DiagnosisAnswer,
  type DiagnosisResult,
} from "../_components/language_training/_diagnosis_questions";

type Status = "answering" | "submitting" | "done" | "error";

interface DraftStorage {
  answers: DiagnosisAnswer[];
  startedAt: string;
}

function storageKey(userId: number | null | undefined) {
  return userId ? `kis-diagnosis-draft-${userId}` : null;
}

function loadDraft(userId: number | null | undefined): DraftStorage | null {
  const key = storageKey(userId);
  if (!key || typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as DraftStorage) : null;
  } catch {
    return null;
  }
}

function saveDraft(userId: number | null | undefined, draft: DraftStorage) {
  const key = storageKey(userId);
  if (!key || typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(draft));
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

export function useLanguageDiagnosis(userId: number | null | undefined) {
  const [answers, setAnswers] = useState<DiagnosisAnswer[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [status, setStatus] = useState<Status>("answering");
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const draft = loadDraft(userId);
    if (draft) {
      setAnswers(draft.answers);
      const next = draft.answers.length < DIAGNOSIS_QUESTIONS.length
        ? draft.answers.length
        : DIAGNOSIS_QUESTIONS.length - 1;
      setCurrentIndex(next);
    }
  }, [userId]);

  const submitAnswer = useCallback(
    (answer: DiagnosisAnswer) => {
      setAnswers((prev) => {
        const without = prev.filter((a) => a.questionId !== answer.questionId);
        const next = [...without, answer].sort((a, b) => a.questionId - b.questionId);
        saveDraft(userId, {
          answers: next,
          startedAt: loadDraft(userId)?.startedAt ?? new Date().toISOString(),
        });
        return next;
      });
      setCurrentIndex((idx) => Math.min(idx + 1, DIAGNOSIS_QUESTIONS.length - 1));
    },
    [userId],
  );

  const goBack = useCallback(() => {
    setCurrentIndex((idx) => Math.max(idx - 1, 0));
  }, []);

  const submit = useCallback(async () => {
    if (answers.length !== DIAGNOSIS_QUESTIONS.length) {
      setErrorMessage("Not all questions answered");
      setStatus("error");
      return;
    }
    setStatus("submitting");
    setErrorMessage(null);
    try {
      const res = await fetch("/api/ai-assistant/language-diagnosis/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ answers }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as DiagnosisResult;
      setResult(data);
      setStatus("done");
      clearDraft(userId);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }, [answers, userId]);

  const retry = useCallback(() => {
    setErrorMessage(null);
    setStatus("answering");
  }, []);

  const abort = useCallback(() => {
    clearDraft(userId);
    setAnswers([]);
    setCurrentIndex(0);
    setResult(null);
    setStatus("answering");
  }, [userId]);

  return {
    questions: DIAGNOSIS_QUESTIONS,
    answers,
    currentIndex,
    status,
    result,
    errorMessage,
    submitAnswer,
    goBack,
    submit,
    retry,
    abort,
  };
}
