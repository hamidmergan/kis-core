"use client";

import { useCallback, useState } from "react";
import { _chunkLabel } from "../_utils";
import type { ExerciseSet } from "../_types";

interface UseExercisesOptions {
  uuid: string;
}

export function useExercises({ uuid }: UseExercisesOptions) {
  const [exerciseSets, setExerciseSets] = useState<ExerciseSet[]>([]);
  const [activeSet, setActiveSet] = useState<ExerciseSet | null>(null);
  const [setCreating, setSetCreating] = useState(false);
  const [createSetTool, setCreateSetTool] = useState<string>("lernkarten");
  const [showCreateModal, setShowCreateModal] = useState(false);

  const loadExerciseSets = useCallback(async (tool?: string) => {
    try {
      const url = tool
        ? `/api/ki-assistent/modules/${uuid}/exercise-sets?tool=${tool}`
        : `/api/ki-assistent/modules/${uuid}/exercise-sets`;
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${setId}`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setActiveSet(data.set);
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const createExerciseSet = useCallback(async (tool: string, mode: string, count: number, sourceUuid?: string) => {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool, mode, count, source_uuid: sourceUuid }),
      });
      if (res.ok) {
        const data = await res.json();
        loadExerciseSets(tool);
        return data.set as ExerciseSet;
      }
    } catch { /* ignore */ }
    return null;
  }, [uuid, loadExerciseSets]);

  const deleteExerciseSet = useCallback(async (setId: number, tool: string) => {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${setId}`, {
        method: "DELETE", credentials: "include",
      });
      loadExerciseSets(tool);
    } catch { /* ignore */ }
  }, [uuid, loadExerciseSets]);

  const downloadExerciseSet = useCallback(async (s: ExerciseSet) => {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${s.id}`, { credentials: "include" });
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

  const submitSingleAnswer = useCallback(async (setId: number, itemId: number, correct: boolean, newRun = false) => {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${setId}/progress`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ results: [{ item_id: itemId, correct }], new_run: newRun }),
      });
    } catch { /* ignore */ }
  }, [uuid]);

  return {
    exerciseSets, setExerciseSets,
    activeSet, setActiveSet,
    setCreating, setSetCreating,
    createSetTool, setCreateSetTool,
    showCreateModal, setShowCreateModal,
    loadExerciseSets, loadExerciseSet,
    createExerciseSet, deleteExerciseSet, downloadExerciseSet,
    submitSingleAnswer,
  };
}
