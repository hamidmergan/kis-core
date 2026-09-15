"use client";
import { useState, useEffect, useCallback } from "react";
import type { Glossary } from "@/types";
import { api } from "@/lib/api";
import { cached, load, publish, subscribe } from "./_glossaryStore";

// Glossaries for translation, per person in the database.

export const MAX_GLOSSARIES = 10;
export const MAX_ENTRIES_PER_GLOSSARY = 500;

// One-time migration of the former browser-only glossaries into the DB.
const LEGACY_KEY = "kis_thl_glossaries";
const MIGRATED_FLAG = "kis_thl_glossaries_migrated";

async function migrateLegacyGlossaries(serverGlossaries: Glossary[]): Promise<Glossary[]> {
  if (typeof window === "undefined") return serverGlossaries;
  if (localStorage.getItem(MIGRATED_FLAG)) return serverGlossaries;

  const raw = localStorage.getItem(LEGACY_KEY);
  // Only migrate while the server is empty, otherwise the second device gets duplicates.
  if (raw && serverGlossaries.length === 0) {
    let legacy: Glossary[] = [];
    try {
      legacy = JSON.parse(raw);
    } catch {
      legacy = [];
    }
    for (const g of legacy.slice(0, MAX_GLOSSARIES)) {
      try {
        await api.postJson<Glossary>("/api/glossaries", {
          name: g.name,
          entries: g.entries ?? {},
        });
      } catch {
        // skip a single bad glossary rather than abort the whole migration
      }
    }
    localStorage.setItem(MIGRATED_FLAG, "1");
    return api.getJson<Glossary[]>("/api/glossaries");
  }

  localStorage.setItem(MIGRATED_FLAG, "1");
  return serverGlossaries;
}

async function fetchGlossaries(): Promise<Glossary[]> {
  const data = await api.getJson<Glossary[]>("/api/glossaries");
  return migrateLegacyGlossaries(data);
}

export function useGlossaries() {
  const [glossaries, setGlossaries] = useState<Glossary[]>(() => cached() ?? []);
  const [loading, setLoading] = useState(() => cached() === null);

  useEffect(() => {
    let cancelled = false;
    const stop = subscribe((list) => {
      if (!cancelled) setGlossaries(list);
    });
    load(fetchGlossaries)
      .catch(() => [] as Glossary[])
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  const createGlossary = useCallback(
    async (name: string, entries: Record<string, string> = {}): Promise<string> => {
      const created = await api.postJson<Glossary>("/api/glossaries", { name, entries });
      publish([...(cached() ?? []), created]);
      return created.id;
    },
    [],
  );

  const updateGlossary = useCallback(
    async (id: string, updates: Partial<Pick<Glossary, "name" | "entries">>): Promise<void> => {
      const updated = await api.patchJson<Glossary>(`/api/glossaries/${id}`, updates);
      publish((cached() ?? []).map(g => (g.id === id ? updated : g)));
    },
    [],
  );

  const deleteGlossary = useCallback(async (id: string): Promise<void> => {
    const res = await api.fetch(`/api/glossaries/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("delete failed");
    publish((cached() ?? []).filter(g => g.id !== id));
  }, []);

  // Up to three glossaries in one call, the first beats the others.
  const mergeEntries = useCallback((ids: string[]): Record<string, string> => {
    const merged: Record<string, string> = {};
    // Iterate from lowest to highest priority so higher-priority entries overwrite
    for (let i = ids.length - 1; i >= 0; i--) {
      const id = ids[i];
      if (!id) continue;
      const g = glossaries.find(g => g.id === id);
      if (!g || Object.keys(g.entries).length === 0) continue;
      Object.assign(merged, g.entries);
    }
    return merged;
  }, [glossaries]);

  const mergeToApiJson = useCallback((ids: string[]): string => {
    const merged = mergeEntries(ids);
    if (Object.keys(merged).length === 0) return "";
    return JSON.stringify(merged);
  }, [mergeEntries]);

  return { glossaries, loading, createGlossary, updateGlossary, deleteGlossary, mergeEntries, mergeToApiJson };
}
