"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import type { WorkspaceStats } from "../_shared";

interface StatsModalProps {
  workspaceUuid: string;
  moduleTitle: string;
  onClose: () => void;
}

export default function StatsModal({ workspaceUuid, onClose }: StatsModalProps) {
  const t = useTranslations("workspace.list");
  const [stats, setStats] = useState<WorkspaceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/lecturer-stats`, {
          credentials: "include",
        });
        if (!res.ok) throw new Error(t("statsLoadError"));
        setStats(await res.json());
      } catch {
        setError(t("statsLoadFailed"));
      } finally {
        setLoading(false);
      }
    })();
  }, [workspaceUuid, t]);

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-background rounded-xl shadow-xl w-80" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-soft">
          <h2 className="text-sm font-semibold">{t("statsTitle")}</h2>
          <IconButton onClick={onClose}>
            <X size={13} weight="bold" />
          </IconButton>
        </div>

        <div className="p-4">
          {loading && <p className="text-sm text-muted text-center py-4">{t("loading")}</p>}
          {error && <p className="text-sm text-error text-center py-4">{error}</p>}

          {stats && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: t("participants"), value: stats.overview.total_enrolled },
                { label: t("active30d"), value: stats.overview.active_30d },
                { label: t("chatRequests"), value: stats.overview.total_chat_messages },
                { label: t("exercisesCreated"), value: stats.overview.total_exercise_sets },
              ].map((item) => (
                <div key={item.label} className="bg-surface rounded-lg px-3 py-2.5">
                  <div className="text-xs text-muted">{item.label}</div>
                  <div className="text-lg font-semibold mt-0.5" style={{ color: "var(--foreground)" }}>
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
