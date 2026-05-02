"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import HelpTooltip from "@/components/ui/HelpTooltip";
import WorkspaceTableRow from "./WorkspaceTableRow";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import type { AccessLink, KiTutorWorkspace } from "../_shared";

const MODULES_PER_PAGE = 20;

interface WorkspaceTableProps {
  workspaces: KiTutorWorkspace[];
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}

export default function WorkspaceTable({
  workspaces,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: WorkspaceTableProps) {
  const t = useTranslations("workspace.list");
  const labels = useWorkspaceLabel();
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(workspaces.length / MODULES_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * MODULES_PER_PAGE;
  const visibleModules = workspaces.slice(startIdx, startIdx + MODULES_PER_PAGE);

  return (
    <>
      <div className="bg-background border border-border-soft rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-xs text-muted uppercase">
                <th className="px-4 py-2 w-6"></th>
                <th className="px-4 py-2">{labels.singular}</th>
                <th className="px-4 py-2 text-right">{t("colSources")}</th>
                <th className="px-4 py-2 text-right">{t("colLinks")}</th>
                <th className="px-4 py-2">
                  <span className="inline-flex items-center gap-1.5">
                    {t("colStatus")}
                    <HelpTooltip text={t("statusHelp")} />
                  </span>
                </th>
                <th className="px-4 py-2"></th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {visibleModules.map((m) => (
                <WorkspaceTableRow
                  key={m.uuid}
                  workspace={m}
                  onToggleActive={onToggleActive}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  onLinksChanged={onLinksChanged}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            {t("paginationInfo", {
              from: startIdx + 1,
              to: Math.min(startIdx + MODULES_PER_PAGE, workspaces.length),
              total: workspaces.length,
              label: labels.plural,
            })}
          </p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage(safePage - 1)}
              disabled={safePage === 1}
              className="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-[var(--foreground)] enabled:hover:outline-2 enabled:hover:outline-[var(--kb)] enabled:hover:text-[var(--kb)] -outline-offset-1"
            >
              {t("prev")}
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => {
              const isActive = p === safePage;
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPage(p)}
                  className={`w-8 h-8 text-sm font-medium rounded-lg transition-colors ${
                    isActive
                      ? "text-white"
                      : "text-[var(--foreground)] hover:outline-2 hover:outline-[var(--kb)] hover:text-[var(--kb)] -outline-offset-1"
                  }`}
                  style={{ backgroundColor: isActive ? "var(--kb)" : "transparent" }}
                >
                  {p}
                </button>
              );
            })}
            <button
              type="button"
              onClick={() => setPage(safePage + 1)}
              disabled={safePage === totalPages}
              className="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-[var(--foreground)] enabled:hover:outline-2 enabled:hover:outline-[var(--kb)] enabled:hover:text-[var(--kb)] -outline-offset-1"
            >
              {t("next")}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
