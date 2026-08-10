import React, { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  BookOpenText,
  Cards,
  ClockCounterClockwise,
  PencilLine,
  Question,
  Table,
  TextAlignLeft,
  TreeStructure,
} from "@phosphor-icons/react";
import { EmptyState } from "@/components/ui/EmptyState";
import { TOOL_COLORS } from "../../_constants";

interface RecentActivity {
  set_id: number;
  tool: string;
  mode: string;
  title: string;
  last_answer: string | null;
  answers: number;
  correct: number;
}

const ACTIVITY_TOOL_ICONS: Record<string, React.ComponentType<any>> = {
  karteikarten: Cards,
  flashcards: BookOpenText,
  quiz: Question,
  grammatik: PencilLine,
  data_table: Table,
  mindmap: TreeStructure,
  wortschatz: TextAlignLeft,
};


export function RecentActivities({ workspaceUuid, onNavigateToSet, refreshKey }: { workspaceUuid: string; onNavigateToSet?: (setId: number, tool: string, mode: string) => void; refreshKey?: number }) {
  const t = useTranslations("workspace.detail.studio.recent");
  const tTools = useTranslations("workspace.detail.langTools");
  const toolLabel = (tool: string) => tTools.has(tool) ? tTools(tool) : tool;
  const locale = useLocale();
  const [activities, setActivities] = useState<RecentActivity[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/recent-activities`, { credentials: "include" })
      .then(r => r.ok ? r.json() : [])
      .then(data => setActivities(data))
      .catch(() => { })
      .finally(() => setLoaded(true));
  }, [workspaceUuid, refreshKey]);

  if (!loaded) return null;

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t("justNow");
    if (diffMin < 60) return t("minutesAgo", { n: diffMin });
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return t("hoursAgo", { n: diffH });
    const diffD = Math.floor(diffH / 24);
    if (diffD === 1) return t("yesterday");
    if (diffD < 7) return t("daysAgo", { n: diffD });
    return d.toLocaleDateString(locale === "en" ? "en-US" : "de-DE", { day: "numeric", month: "short" });
  };

  if (activities.length === 0) {
    return (
      <EmptyState
        className="pt-16"
        icon={<ClockCounterClockwise size={32} weight="bold" />}
        text={t("empty")}
      />
    );
  }

  return (
    <div className="px-3 pb-3">
      <span className="text-xs font-semibold uppercase tracking-wider my-2 block" style={{ color: "var(--muted)" }}>
        {t("heading")}
      </span>
      <div className="flex flex-col gap-1">
        {activities.map((a) => {
          const iconColor = TOOL_COLORS[a.tool]?.color ?? "var(--muted)";
          const Icon = ACTIVITY_TOOL_ICONS[a.tool] ?? Cards;
          const displayTitle = a.title.replace(/\.(pdf|mp4|mp3|webm|wav|m4a|ogg)$/i, "");
          return (
            <button
              key={`${a.set_id}-${a.tool}-${a.mode}`}
              type="button"
              onClick={() => onNavigateToSet?.(a.set_id, a.tool, a.mode)}
              className="flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-left border-2 border-transparent transition-colors hover:border-[var(--tile-color)]"
              style={{ backgroundColor: "var(--hover)", ["--tile-color" as string]: iconColor }}
            >
              <div className="w-7 h-7 flex items-center justify-center flex-shrink-0">
                <Icon size={16} color={iconColor} weight="bold" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate" style={{ color: "var(--foreground)" }}>
                  {displayTitle}
                </div>
                <div className="text-xs" style={{ color: "var(--muted)" }}>
                  {toolLabel(a.tool)} · {a.last_answer ? formatTime(a.last_answer) : ""}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

