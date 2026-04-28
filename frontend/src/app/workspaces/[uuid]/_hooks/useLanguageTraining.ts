"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ClozeExercise, GlossaryEntry, LanguageTrainingView, VocabTestQuestion } from "../_types";

interface UseLanguageTrainingOptions {
  uuid: string;
  langTrainingActiveIds: string[];
  onAfterCloze?: () => void;
  onAfterVocabTest?: () => void;
}

export function useLanguageTraining({ uuid, langTrainingActiveIds, onAfterCloze, onAfterVocabTest }: UseLanguageTrainingOptions) {
  const [langTrainingView, setSprachView] = useState<LanguageTrainingView>("overview");
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [glossaryLoading, setGlossaryLoading] = useState(false);
  const [clozeExercises, setClozeExercises] = useState<ClozeExercise[]>([]);
  const [clozeLoading, setClozeLoading] = useState(false);
  const [vocabQuestions, setVocabQuestions] = useState<VocabTestQuestion[]>([]);
  const [vocabLoading, setVocabLoading] = useState(false);
  const [langTrainingSourceUuid, setSprachSourceUuid] = useState("");
  const [glossaryCount, setGlossaryCount] = useState(0);
  const [glossaryExtracting, setGlossaryExtracting] = useState(false);
  const [glossaryFeedback, setGlossaryFeedback] = useState<{ kind: "success" | "info" | "error"; message: string } | null>(null);

  const glossaryPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const glossaryFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopGlossaryPolling = useCallback(() => {
    if (glossaryPollRef.current) { clearInterval(glossaryPollRef.current); glossaryPollRef.current = null; }
  }, []);

  const showFeedback = useCallback((kind: "success" | "info" | "error", message: string) => {
    if (glossaryFeedbackTimerRef.current) clearTimeout(glossaryFeedbackTimerRef.current);
    setGlossaryFeedback({ kind, message });
    glossaryFeedbackTimerRef.current = setTimeout(() => setGlossaryFeedback(null), 6000);
  }, []);

  const dismissFeedback = useCallback(() => {
    if (glossaryFeedbackTimerRef.current) clearTimeout(glossaryFeedbackTimerRef.current);
    setGlossaryFeedback(null);
  }, []);

  const loadGlossary = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai-assistant/modules/${uuid}/glossary`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGlossary(data.entries || []);
        return data.entries?.length > 0;
      }
    } catch { /* ignore */ }
    return false;
  }, [uuid]);

  const loadGlossaryCount = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai-assistant/modules/${uuid}/glossary-count`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGlossaryCount(data.count);
      }
    } catch { /* ignore */ }
  }, [uuid]);

  useEffect(() => {
    loadGlossary();
    loadGlossaryCount();
    return () => stopGlossaryPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid]);

  const deleteGlossaryEntry = useCallback(async (entryId: number) => {
    try {
      await fetch(`/api/ai-assistant/modules/${uuid}/glossary/${entryId}`, {
        method: "DELETE", credentials: "include",
      });
      setGlossary((prev) => prev.filter((e) => e.id !== entryId));
      loadGlossaryCount();
    } catch { /* ignore */ }
  }, [uuid, loadGlossaryCount]);

  const deleteAllGlossaryEntries = useCallback(async () => {
    try {
      await fetch(`/api/ai-assistant/modules/${uuid}/glossary`, {
        method: "DELETE", credentials: "include",
      });
      setGlossary([]);
      loadGlossaryCount();
    } catch { /* ignore */ }
  }, [uuid, loadGlossaryCount]);

  const generateGlossary = useCallback(async () => {
    if (langTrainingActiveIds.length === 0) return;
    setGlossaryLoading(true);
    try {
      const res = await fetch(`/api/ai-assistant/modules/${uuid}/glossary/generate`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: langTrainingActiveIds }),
      });
      if (res.ok) {
        stopGlossaryPolling();
        const startCount = glossary.length;
        glossaryPollRef.current = setInterval(async () => {
          const hasNew = await loadGlossary();
          if (hasNew) {
            const res2 = await fetch(`/api/ai-assistant/modules/${uuid}/glossary`, { credentials: "include" });
            if (res2.ok) {
              const data2 = await res2.json();
              if ((data2.entries || []).length !== startCount) {
                setGlossary(data2.entries || []);
                setGlossaryLoading(false);
                stopGlossaryPolling();
                loadGlossaryCount();
              }
            }
          }
        }, 3000);
        setTimeout(() => { stopGlossaryPolling(); setGlossaryLoading(false); }, 120000);
      } else {
        setGlossaryLoading(false);
      }
    } catch {
      setGlossaryLoading(false);
    }
  }, [uuid, langTrainingActiveIds, glossary.length, loadGlossary, loadGlossaryCount, stopGlossaryPolling]);

  const generateCloze = useCallback(async () => {
    if (langTrainingActiveIds.length === 0) return;
    setClozeLoading(true);
    try {
      const res = await fetch(`/api/ai-assistant/modules/${uuid}/exercises/cloze`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: langTrainingActiveIds }),
      });
      if (res.ok) {
        onAfterCloze?.();
        setSprachView("cl-sets");
      }
    } catch { /* ignore */ } finally {
      setClozeLoading(false);
    }
  }, [uuid, langTrainingActiveIds, onAfterCloze]);

  const generateVocabTest = useCallback(async () => {
    if (langTrainingActiveIds.length === 0) return;
    setVocabLoading(true);
    try {
      const res = await fetch(`/api/ai-assistant/modules/${uuid}/exercises/vocab-test`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: langTrainingActiveIds }),
      });
      if (res.ok) {
        onAfterVocabTest?.();
        setSprachView("vt-sets");
      }
    } catch { /* ignore */ } finally {
      setVocabLoading(false);
    }
  }, [uuid, langTrainingActiveIds, onAfterVocabTest]);

  const extractGlossary = useCallback(async (text: string, sourceUuid: string, page: number) => {
    setGlossaryFeedback(null);
    setGlossaryExtracting(true);
    try {
      const res = await fetch(`/api/ai-assistant/modules/${uuid}/glossary/extract`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source_uuid: sourceUuid, page_number: page }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.added > 0) {
          loadGlossary();
          loadGlossaryCount();
          showFeedback("success", data.message || `${data.added} Begriff(e) hinzugefügt.`);
        } else {
          showFeedback("info", data.message || "Keine neuen Begriffe gefunden.");
        }
      } else {
        showFeedback("error", "Extraktion fehlgeschlagen. Bitte erneut versuchen.");
      }
    } catch {
      showFeedback("error", "Netzwerkfehler. Bitte erneut versuchen.");
    } finally {
      setGlossaryExtracting(false);
    }
  }, [uuid, loadGlossary, loadGlossaryCount, showFeedback]);

  return {
    langTrainingView, setSprachView,
    glossary, glossaryLoading, glossaryCount, glossaryExtracting, glossaryFeedback,
    clozeExercises, clozeLoading,
    vocabQuestions, vocabLoading,
    langTrainingSourceUuid, setSprachSourceUuid,
    deleteGlossaryEntry, deleteAllGlossaryEntries,
    generateGlossary, generateCloze, generateVocabTest,
    loadGlossary, loadGlossaryCount,
    extractGlossary, showFeedback, dismissFeedback,
  };
}
