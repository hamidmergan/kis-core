"use client";
import { useState, useEffect, useCallback } from "react";
import type { Glossary } from "@/types";
import { api } from "@/lib/api";

// Terminology glossaries for the translation tool. Persisted per user in the
// DB (see backend/src/routes/glossaries.py). All consumers use this hook
// exclusively, so no other changes are needed to switch storage backends.

export const MAX_GLOSSARIES = 10;
export const MAX_ENTRIES_PER_GLOSSARY = 500;

// One-time migration of the former browser-only glossaries into the DB.
const LEGACY_KEY = "kis_thl_glossaries";
const MIGRATED_FLAG = "kis_thl_glossaries_migrated";

async function migrateLegacyGlossaries(serverGlossaries: Glossary[]): Promise<Glossary[]> {
  if (typeof window === "undefined") return serverGlossaries;
  if (localStorage.getItem(MIGRATED_FLAG)) return serverGlossaries;

  const raw = localStorage.getItem(LEGACY_KEY);
  // Only migrate when the server side is still empty, so re-running on a second
  // device (with its own leftover localStorage) cannot create duplicates.
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

export function useGlossaries() {
  const [glossaries, setGlossaries] = useState<Glossary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let data = await api.getJson<Glossary[]>("/api/glossaries");
        data = await migrateLegacyGlossaries(data);
        if (!cancelled) setGlossaries(data);
      } catch {
        if (!cancelled) setGlossaries([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const createGlossary = useCallback(
    async (name: string, entries: Record<string, string> = {}): Promise<string> => {
      const created = await api.postJson<Glossary>("/api/glossaries", { name, entries });
      setGlossaries(prev => [...prev, created]);
      return created.id;
    },
    [],
  );

  const updateGlossary = useCallback(
    async (id: string, updates: Partial<Pick<Glossary, "name" | "entries">>): Promise<void> => {
      const updated = await api.patchJson<Glossary>(`/api/glossaries/${id}`, updates);
      setGlossaries(prev => prev.map(g => (g.id === id ? updated : g)));
    },
    [],
  );

  const deleteGlossary = useCallback(async (id: string): Promise<void> => {
    const res = await api.fetch(`/api/glossaries/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("delete failed");
    setGlossaries(prev => prev.filter(g => g.id !== id));
  }, []);

  // Merge up to 3 glossary IDs into a single JSON string for API calls.
  // Index 0 has highest priority — its entries overwrite conflicts from index 1 and 2.
  const mergeToApiJson = useCallback((ids: string[]): string => {
    const merged: Record<string, string> = {};
    // Iterate from lowest to highest priority so higher-priority entries overwrite
    for (let i = ids.length - 1; i >= 0; i--) {
      const id = ids[i];
      if (!id) continue;
      const g = glossaries.find(g => g.id === id);
      if (!g || Object.keys(g.entries).length === 0) continue;
      Object.assign(merged, g.entries);
    }
    if (Object.keys(merged).length === 0) return "";
    return JSON.stringify(merged);
  }, [glossaries]);

  return { glossaries, loading, createGlossary, updateGlossary, deleteGlossary, mergeToApiJson };
}
