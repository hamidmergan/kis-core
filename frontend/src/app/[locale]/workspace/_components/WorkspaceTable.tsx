"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import WorkspaceGroupTable from "./WorkspaceGroupTable";
import { canManage, type AccessLink, type KiTutorWorkspace } from "../_shared";

// Below this count a section opens by itself, above it stays collapsed until clicked.
const AUTO_OPEN_MAX = 10;

interface WorkspaceTableProps {
  workspaces: KiTutorWorkspace[];
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onToggleFavorite: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string, tourModule: boolean | null) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
  onRolesChanged: () => void;
  onLeaveDemo?: (uuid: string) => void;
}

/** Favorites first, then what the person manages, then what they are enrolled in. */
export default function WorkspaceTable({ workspaces, ...groupProps }: WorkspaceTableProps) {
  const t = useTranslations("workspace.list");

  const favorites = useMemo(() => workspaces.filter((m) => m.is_favorite), [workspaces]);
  const mine = useMemo(() => workspaces.filter((m) => canManage(m.access)), [workspaces]);
  const enrolled = useMemo(() => workspaces.filter((m) => !canManage(m.access)), [workspaces]);

  return (
    <div className="flex flex-col gap-4">
      {favorites.length > 0 && (
        <CollapsibleCard title={t("groupFavorites")} defaultOpen headerBg>
          <WorkspaceGroupTable workspaces={favorites} {...groupProps} />
        </CollapsibleCard>
      )}
      {mine.length > 0 && (
        <CollapsibleCard title={t("myWorkspaces", { label: "Workspaces" })} defaultOpen={mine.length <= AUTO_OPEN_MAX} headerBg>
          <WorkspaceGroupTable workspaces={mine} {...groupProps} />
        </CollapsibleCard>
      )}
      {enrolled.length > 0 && (
        <CollapsibleCard title={t("groupEnrolled")} defaultOpen={enrolled.length <= AUTO_OPEN_MAX} headerBg>
          <WorkspaceGroupTable workspaces={enrolled} {...groupProps} />
        </CollapsibleCard>
      )}
    </div>
  );
}
