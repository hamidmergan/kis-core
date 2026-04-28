"use client";

import { useEffect, useState } from "react";
import { X } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import type { ModuleStats } from "../_shared";

interface StatsModalProps {
  moduleUuid: string;
  moduleTitle: string;
  onClose: () => void;
}

export default function StatsModal({ moduleUuid, onClose }: StatsModalProps) {
  const [stats, setStats] = useState<ModuleStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ai-assistant/modules/${moduleUuid}/dozent-stats`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error("Fehler beim Laden");
        setStats(await res.json());
      } catch {
        setError("Statistiken konnten nicht geladen werden.");
      } finally {
        setLoading(false);
      }
    })();
  }, [moduleUuid]);

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-80" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-sm font-semibold">Statistik</h2>
          <IconButton onClick={onClose}>
            <X size={13} weight="bold" />
          </IconButton>
        </div>

        <div className="p-4">
          {loading && <p className="text-sm text-gray-500 text-center py-4">Laden...</p>}
          {error && <p className="text-sm text-red-600 text-center py-4">{error}</p>}

          {stats && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Teilnehmer", value: stats.overview.total_enrolled },
                { label: "Aktiv (30 Tage)", value: stats.overview.active_30d },
                { label: "Chat-Anfragen", value: stats.overview.total_chat_messages },
                { label: "Erstellte Übungen", value: stats.overview.total_exercise_sets },
              ].map((item) => (
                <div key={item.label} className="bg-gray-50 rounded-lg px-3 py-2.5">
                  <div className="text-xs text-gray-500">{item.label}</div>
                  <div className="text-lg font-semibold mt-0.5" style={{ color: "var(--text)" }}>
                    {item.value}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
