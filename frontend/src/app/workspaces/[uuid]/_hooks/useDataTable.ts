"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DatentabelleData, DatentabelleSource } from "../_types";

interface UseDatentabelleOptions {
  uuid: string;
  selectedSourceIds: string[];
}

export function useDatentabelle({ uuid, selectedSourceIds }: UseDatentabelleOptions) {
  const [datentabelle, setDatentabelle] = useState<DatentabelleData | null>(null);
  const [datentabelleSources, setDatentabelleSources] = useState<DatentabelleSource[]>([]);
  const [datentabelleLoading, setDatentabelleLoading] = useState(false);
  const [datentabelleList, setDatentabelleList] = useState<{ id: number; title: string; created_at: string | null }[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const refreshList = useCallback(async () => {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabellen`, { credentials: "include" });
      if (res.ok) setDatentabelleList(await res.json());
    } catch { /* ignore */ }
  }, [uuid]);

  const startPolling = useCallback((dtId: number) => {
    stopPolling();
    setDatentabelleLoading(true);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/${dtId}`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.table_data) {
          setDatentabelle(data.table_data);
          setDatentabelleSources(data.sources || data.table_data.sources || []);
          setDatentabelleLoading(false);
          stopPolling();
          refreshList();
        } else if (data.status === "failed") {
          console.error("Datentabelle failed:", data.error);
          setDatentabelleLoading(false);
          stopPolling();
        }
      } catch { /* ignore */ }
    }, 3000);
  }, [uuid, stopPolling, refreshList]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          if (data && data.status === "success" && data.table_data) {
            setDatentabelle(data.table_data);
            setDatentabelleSources(data.sources || data.table_data.sources || []);
          } else if (data && (data.status === "pending" || data.status === "running")) {
            startPolling(data.id);
          }
        }
      } catch { /* ignore */ }
    })();
    refreshList();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid]);

  const generate = useCallback(async () => {
    if (selectedSourceIds.length === 0) return;
    setDatentabelleLoading(true);
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/generate`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: selectedSourceIds.slice(0, 5) }),
      });
      if (res.ok) {
        const data = await res.json();
        startPolling(data.datentabelle_id);
      } else {
        console.error("Datentabelle generate error:", res.status);
        setDatentabelleLoading(false);
      }
    } catch {
      setDatentabelleLoading(false);
    }
  }, [uuid, selectedSourceIds, startPolling]);

  const select = useCallback(async (id: number) => {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/${id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && data.table_data) {
        setDatentabelle(data.table_data);
        setDatentabelleSources(data.sources || data.table_data.sources || []);
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const remove = useCallback(async (id: number) => {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/${id}`, { method: "DELETE", credentials: "include" });
      setDatentabelleList((prev) => prev.filter((d) => d.id !== id));
    } catch { /* ignore */ }
  }, [uuid]);

  return {
    datentabelle, datentabelleSources, datentabelleLoading, datentabelleList,
    generate, select, remove,
  };
}
