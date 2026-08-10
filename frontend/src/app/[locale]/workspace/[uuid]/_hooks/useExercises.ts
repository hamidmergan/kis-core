"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { _chunkLabel } from "../_utils";
import type { ExerciseSet } from "../_types";

interface UseExercisesOptions {
  uuid: string;
}

export function useExercises({ uuid }: UseExercisesOptions) {
  const [exerciseSets, setExerciseSets] = useState<ExerciseSet[]>([]);
  const [activeSet, setActiveSet] = useState<ExerciseSet | null>(null);
  const [createSetTool, setCreateSetTool] = useState<string>("flashcards");
  const [showCreateModal, setShowCreateModal] = useState(false);

  const loadExerciseSets = useCallback(async (tool?: string) => {
    try {
      const url = tool
        ? `/api/ai-assistant/workspaces/${uuid}/exercise-sets?tool=${tool}`
        : `/api/ai-assistant/workspaces/${uuid}/exercise-sets`;
      const res = await fetch(url, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        const newSets: ExerciseSet[] = data.sets || [];
        if (tool) {
          setExerciseSets((prev) => [
            ...prev.filter((s) => s.tool !== tool),
            ...newSets,
          ]);
        } else {
          setExerciseSets(newSets);
        }
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const loadExerciseSet = useCallback(async (setId: number) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/exercise-sets/${setId}`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setActiveSet(data.set);
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const createExerciseSet = useCallback(async (tool: string, mode: string, count: number, sourceUuids?: string[], grammarTopicId?: number, grammarKinds?: string[]) => {
    try {
      // api.fetch attaches Accept-Language from the NEXT_LOCALE cookie so the
      // backend generates the set in the UI language (raw fetch defaulted to de).
      const res = await api.fetch(`/api/ai-assistant/workspaces/${uuid}/exercise-sets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // source_uuids covers every selected source; source_uuid stays for the older
        // single-source contract the backend still accepts.
        body: JSON.stringify({
          tool, mode, count,
          source_uuids: sourceUuids,
          source_uuid: sourceUuids?.[0],
          // Only the grammar tool sends this; the backend rejects an unknown id.
          grammar_topic_id: grammarTopicId,
          // Nur die Grammatik-Uebung sendet das, und auch die nur bei einer echten
          // Auswahl. Fehlt es, ist das Set gemischt.
          grammar_kinds: grammarKinds,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        loadExerciseSets(tool);
        return data.set as ExerciseSet;
      }
    } catch { /* ignore */ }
    return null;
  }, [uuid, loadExerciseSets]);

  // Run a failed set again. The card keeps its id and flips straight back to
  // "generating" so the learner sees the same card retrying, not a new one.
  const retryExerciseSet = useCallback(async (setId: number, tool: string) => {
    setExerciseSets((prev) => prev.map((s) => (
      s.id === setId ? { ...s, status: "generating" } : s
    )));
    try {
      const res = await api.fetch(`/api/ai-assistant/workspaces/${uuid}/exercise-sets/${setId}/retry`, {
        method: "POST",
      });
      if (!res.ok) {
        // Quota, burst limit or an already-running set: put the card back to failed
        // rather than leaving it spinning forever on a task that was never queued.
        loadExerciseSets(tool);
        return false;
      }
      // Same watch the create flow runs, so the card leaves "generating" on its own.
      const poll = setInterval(() => loadExerciseSets(tool), 3000);
      setTimeout(() => clearInterval(poll), 120000);
      return true;
    } catch {
      loadExerciseSets(tool);
      return false;
    }
  }, [uuid, loadExerciseSets]);

  const deleteExerciseSet = useCallback(async (setId: number, tool: string) => {
    try {
      await fetch(`/api/ai-assistant/workspaces/${uuid}/exercise-sets/${setId}`, {
        method: "DELETE", credentials: "include",
      });
      loadExerciseSets(tool);
    } catch { /* ignore */ }
  }, [uuid, loadExerciseSets]);

  const downloadExerciseSet = useCallback(async (s: ExerciseSet) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/exercise-sets/${s.id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      const set = data.set as ExerciseSet;
      const items = set.items || [];
      const lines: string[] = [];
      lines.push(set.title);
      lines.push("=".repeat(set.title.length));
      lines.push("");
      items.forEach((item, i) => {
        lines.push(`${i + 1}. ${item.front}`);
        lines.push("");
        lines.push(`   ${item.back.replace(/\n/g, "\n   ")}`);
        if (item.back_en) lines.push(`   EN: ${item.back_en}`);
        if (item.extras?.word_parts) {
          lines.push(`   Wortzerlegung: ${item.extras.word_parts}`);
          if (item.extras.word_parts_explained) {
            lines.push(`     ${item.extras.word_parts_explained}`);
          }
        }
        if (item.extras?.example_sentence) {
          lines.push(`   Beispiel: „${item.extras.example_sentence}"`);
        }
        const sources = item.sources?.length
          ? item.sources
          : (item.source_label ? [{ source_label: item.source_label, page_number: item.page_number, start_time: item.start_time, highlight_text: undefined }] : []);
        if (sources.length > 0) {
          lines.push(`   Quellen:`);
          sources.forEach((sr) => {
            const label = sr.page_number
              ? `, ${_chunkLabel(sr.source_label, sr.page_number, sr.start_time)}`
              : "";
            lines.push(`     - ${sr.source_label}${label}`);
            if (sr.highlight_text) {
              lines.push(`       „${sr.highlight_text.replace(/\n/g, " ").trim()}"`);
            }
          });
        }
        lines.push("");
      });
      const text = lines.join("\n");
      const safeTitle = (set.title || set.tool || "karteikarten").replace(/[^a-zA-Z0-9äöüÄÖÜß_-]+/g, "_").slice(0, 60);
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${safeTitle}_${set.id}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  }, [uuid]);

  const submitSingleAnswer = useCallback(async (setId: number, itemId: number, correct: boolean) => {
    try {
      await fetch(`/api/ai-assistant/workspaces/${uuid}/exercise-sets/${setId}/progress`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ results: [{ item_id: itemId, correct }] }),
      });
    } catch { /* ignore */ }
  }, [uuid]);

  return {
    exerciseSets, setExerciseSets,
    activeSet, setActiveSet,
    createSetTool, setCreateSetTool,
    showCreateModal, setShowCreateModal,
    loadExerciseSets, loadExerciseSet,
    createExerciseSet, deleteExerciseSet, retryExerciseSet, downloadExerciseSet,
    submitSingleAnswer,
  };
}
