"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DataTableData, DataTableSource } from "../_types";

interface UseDataTableOptions {
  uuid: string;
  selectedSourceIds: string[];
}

export function useDataTable({ uuid, selectedSourceIds }: UseDataTableOptions) {
  const [data_table, setDataTable] = useState<DataTableData | null>(null);
  const [data_tableSources, setDataTableSources] = useState<DataTableSource[]>([]);
  const [data_tableLoading, setDataTableLoading] = useState(false);
  const [data_tableList, setDataTableList] = useState<{ id: number; title: string; created_at: string | null }[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const refreshList = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/data_tables`, { credentials: "include" });
      if (res.ok) setDataTableList(await res.json());
    } catch { /* ignore */ }
  }, [uuid]);

  const startPolling = useCallback((dtId: number) => {
    stopPolling();
    setDataTableLoading(true);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/data_table/${dtId}`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.table_data) {
          setDataTable(data.table_data);
          setDataTableSources(data.sources || data.table_data.sources || []);
          setDataTableLoading(false);
          stopPolling();
          refreshList();
        } else if (data.status === "failed") {
          console.error("DataTable failed:", data.error);
          setDataTableLoading(false);
          stopPolling();
        }
      } catch { /* ignore */ }
    }, 3000);
  }, [uuid, stopPolling, refreshList]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/data_table`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          if (data && data.status === "success" && data.table_data) {
            setDataTable(data.table_data);
            setDataTableSources(data.sources || data.table_data.sources || []);
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
    setDataTableLoading(true);
    try {
      // api.fetch attaches Accept-Language from the NEXT_LOCALE cookie so the
      // table is generated in the UI language (raw fetch defaulted to de).
      const res = await api.fetch(`/api/ai-assistant/workspaces/${uuid}/data_table/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: selectedSourceIds.slice(0, 5) }),
      });
      if (res.ok) {
        const data = await res.json();
        startPolling(data.data_table_id);
      } else {
        console.error("DataTable generate error:", res.status);
        setDataTableLoading(false);
      }
    } catch {
      setDataTableLoading(false);
    }
  }, [uuid, selectedSourceIds, startPolling]);

  const select = useCallback(async (id: number) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/data_table/${id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && data.table_data) {
        setDataTable(data.table_data);
        setDataTableSources(data.sources || data.table_data.sources || []);
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const remove = useCallback(async (id: number) => {
    try {
      await fetch(`/api/ai-assistant/workspaces/${uuid}/data_table/${id}`, { method: "DELETE", credentials: "include" });
      setDataTableList((prev) => prev.filter((d) => d.id !== id));
    } catch { /* ignore */ }
  }, [uuid]);

  // Wirft bei Fehler weiter, anders als die Nachbarn hier: beim Umbenennen sieht
  // jemand zu und das Feld soll den Grund zeigen koennen.
  const rename = useCallback(async (id: number, title: string) => {
    const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/data_table/${id}/title`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "");
    const daten = await res.json();
    // Direkt in der Liste ersetzen statt neu laden: der Name steht sofort, ohne
    // dass die ganze Liste flackert.
    setDataTableList((prev) => prev.map((d) => (d.id === id ? { ...d, title: daten.title } : d)));
  }, [uuid]);

  return {
    data_table, data_tableSources, data_tableLoading, data_tableList,
    generate, select, remove, rename,
  };
}
