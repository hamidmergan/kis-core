"use client";

import React, { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import HelpTooltip from "@/components/ui/HelpTooltip";
import WorkspaceTableRow from "./WorkspaceTableRow";
import WorkspaceTableStudentRow from "./WorkspaceTableStudentRow";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { canManage, type AccessLink, type KiTutorWorkspace } from "../_shared";

const MODULES_PER_PAGE = 20;

interface WorkspaceTableProps {
  workspaces: KiTutorWorkspace[];
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
  onRolesChanged: () => void;
  onLeaveDemo?: (uuid: string) => void;
}

export default function WorkspaceTable({
  workspaces,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
  onRolesChanged,
  onLeaveDemo,
}: WorkspaceTableProps) {
  const t = useTranslations("workspace.list");
  const labels = useWorkspaceLabel();
  const [page, setPage] = useState(1);

  // Workspaces the user runs come first, the ones they only learn from after.
  // Sorting before paginating keeps the two groups from interleaving across pages.
  const sorted = useMemo(
    () => [...workspaces].sort(
      (a, b) => Number(canManage(b.access)) - Number(canManage(a.access)),
    ),
    [workspaces],
  );
  const hasBothGroups = sorted.some((m) => canManage(m.access))
    && sorted.some((m) => !canManage(m.access));

  const totalPages = Math.max(1, Math.ceil(sorted.length / MODULES_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * MODULES_PER_PAGE;
  const visibleModules = sorted.slice(startIdx, startIdx + MODULES_PER_PAGE);

  // A heading goes above the first row of a page and wherever the group changes,
  // so every page says what it is showing even when a group spans pages.
  const groupHeadingFor = (index: number): string | null => {
    if (!hasBothGroups) return null;
    const current = canManage(visibleModules[index].access);
    if (index > 0 && canManage(visibleModules[index - 1].access) === current) return null;
    return current ? t("myWorkspaces", { label: labels.plural }) : t("groupEnrolled");
  };

  return (
    <>
      <div className="bg-background rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-190 text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-xs text-muted uppercase">
                <th className="px-4 py-2">{labels.singular}</th>
                <th className="pl-6 pr-4 py-2 text-right">{t("colSources")}</th>
                <th className="pl-20 pr-4 py-2 text-right">{t("colLinks")}</th>
                <th className="pl-20 pr-4 py-2">
                  <span className="inline-flex items-center gap-1.5">
                    {t("colStatus")}
                    <HelpTooltip text={t("statusHelp")} />
                  </span>
                </th>
                <th className="pl-20 pr-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {visibleModules.map((m, i) => {
                const heading = groupHeadingFor(i);
                return (
                  <React.Fragment key={`${m.uuid}-${m.access}-${m.enrollment_id ?? "o"}`}>
                    {heading && (
                      <tr>
                        <th
                          colSpan={5}
                          scope="colgroup"
                          className="px-4 pt-5 pb-2 text-left text-xs font-semibold uppercase tracking-wide"
                          style={{ color: "var(--muted)" }}
                        >
                          {heading}
                        </th>
                      </tr>
                    )}
                    {canManage(m.access) ? (
                      <WorkspaceTableRow
                        workspace={m}
                        onToggleActive={onToggleActive}
                        onDelete={onDelete}
                        onEdit={onEdit}
                        onLinksChanged={onLinksChanged}
                        onRolesChanged={onRolesChanged}
                      />
                    ) : (
                      <WorkspaceTableStudentRow
                        workspace={m}
                        onLeave={onLeaveDemo}
                      />
                    )}
                  </React.Fragment>
                );
              })}
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
