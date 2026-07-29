"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { GlossaryEntry, LanguageTrainingView } from "../_types";

interface UseLanguageTrainingOptions {
  uuid: string;
}

export function useLanguageTraining({ uuid }: UseLanguageTrainingOptions) {
  const t = useTranslations("workspace.detail.errors");
  const [langTrainingView, setSprachView] = useState<LanguageTrainingView>("overview");
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [glossaryCount, setGlossaryCount] = useState(0);
  const [glossaryExtracting, setGlossaryExtracting] = useState(false);
  const [glossaryFeedback, setGlossaryFeedback] = useState<{ kind: "success" | "info" | "error"; message: string } | null>(null);

  const glossaryFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/glossary`, { credentials: "include" });
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
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/glossary-count`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGlossaryCount(data.count);
      }
    } catch { /* ignore */ }
  }, [uuid]);

  useEffect(() => {
    loadGlossary();
    loadGlossaryCount();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid]);

  const deleteGlossaryEntry = useCallback(async (entryId: number) => {
    try {
      await fetch(`/api/ai-assistant/workspaces/${uuid}/glossary/${entryId}`, {
        method: "DELETE", credentials: "include",
      });
      setGlossary((prev) => prev.filter((e) => e.id !== entryId));
      loadGlossaryCount();
    } catch { /* ignore */ }
  }, [uuid, loadGlossaryCount]);

  const deleteAllGlossaryEntries = useCallback(async () => {
    try {
      await fetch(`/api/ai-assistant/workspaces/${uuid}/glossary`, {
        method: "DELETE", credentials: "include",
      });
      setGlossary([]);
      loadGlossaryCount();
    } catch { /* ignore */ }
  }, [uuid, loadGlossaryCount]);

  const extractGlossary = useCallback(async (text: string, sourceUuid: string, page: number) => {
    setGlossaryFeedback(null);
    setGlossaryExtracting(true);
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/glossary/extract`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source_uuid: sourceUuid, page_number: page }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.added > 0) {
          loadGlossary();
          loadGlossaryCount();
          showFeedback("success", data.message || t("termsAdded", { count: data.added }));
        } else {
          showFeedback("info", data.message || t("noNewTerms"));
        }
      } else {
        showFeedback("error", t("extractionFailed"));
      }
    } catch {
      showFeedback("error", t("networkRetry"));
    } finally {
      setGlossaryExtracting(false);
    }
  }, [uuid, loadGlossary, loadGlossaryCount, showFeedback]);

  return {
    langTrainingView, setSprachView,
    glossary, glossaryCount, glossaryExtracting, glossaryFeedback,
    deleteGlossaryEntry, deleteAllGlossaryEntries,
    loadGlossary, loadGlossaryCount,
    extractGlossary, showFeedback, dismissFeedback,
  };
}
