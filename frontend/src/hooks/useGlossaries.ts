"use client";
import { useState, useEffect, useCallback } from "react";
import type { Glossary } from "@/types";

// TODO: Replace localStorage with API calls when LDAP/DB is available.
// All consumers use this hook exclusively — no other changes needed.

const STORAGE_KEY = "kis_thl_glossaries";

export const MAX_GLOSSARIES = 10;
export const MAX_ENTRIES_PER_GLOSSARY = 500;

export function useGlossaries() {
  const [glossaries, setGlossaries] = useState<Glossary[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setGlossaries(JSON.parse(raw));
    } catch {}
  }, []);

  // Persist to localStorage on every change
  const persist = useCallback((updated: Glossary[]) => {
    setGlossaries(updated);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }, []);

  const createGlossary = useCallback((name: string) => {
    const g: Glossary = {
      id: crypto.randomUUID(),
      name,
      entries: {},
      createdAt: new Date().toISOString(),
    };
    persist([...glossaries, g]);
    return g.id;
  }, [glossaries, persist]);

  const updateGlossary = useCallback((id: string, updates: Partial<Pick<Glossary, "name" | "entries">>) => {
    persist(glossaries.map(g => g.id === id ? { ...g, ...updates } : g));
  }, [glossaries, persist]);

  const deleteGlossary = useCallback((id: string) => {
    persist(glossaries.filter(g => g.id !== id));
  }, [glossaries, persist]);

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

  return { glossaries, createGlossary, updateGlossary, deleteGlossary, mergeToApiJson };
}
