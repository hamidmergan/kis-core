"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Files } from "@phosphor-icons/react";
import HelpTooltip from "@/components/ui/HelpTooltip";
import WorkspaceTableRow from "./WorkspaceTableRow";
import WorkspaceTableStudentRow from "./WorkspaceTableStudentRow";
import { canManage, type AccessLink, type KiTutorWorkspace } from "../_shared";

const MODULES_PER_PAGE = 20;

interface WorkspaceGroupTableProps {
  workspaces: KiTutorWorkspace[];
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onToggleFavorite: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string, tourModule: boolean | null) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
  onRolesChanged: () => void;
  onLeaveDemo?: (uuid: string) => void;
}

/** One section's table (favorites, mine or enrolled), paginated on its own. */
export default function WorkspaceGroupTable({
  workspaces,
  onToggleActive,
  onToggleFavorite,
  onDelete,
  onEdit,
  onLinksChanged,
  onRolesChanged,
  onLeaveDemo,
}: WorkspaceGroupTableProps) {
  const t = useTranslations("workspace.list");
  const [page, setPage] = useState(1);

  // Manageable rows before learner rows, relevant when favorites mix both.
  const sorted = useMemo(
    () => [...workspaces].sort(
      (a, b) => Number(canManage(b.access)) - Number(canManage(a.access)),
    ),
    [workspaces],
  );
  // Links and status only concern owners and tutors, a pure learner never sees them.
  const manageColumns = sorted.some((m) => canManage(m.access));

  const totalPages = Math.max(1, Math.ceil(sorted.length / MODULES_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * MODULES_PER_PAGE;
  const visibleModules = sorted.slice(startIdx, startIdx + MODULES_PER_PAGE);

  return (
    <>
      <div className="bg-background rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className={`w-full text-sm ${manageColumns ? "sm:min-w-160" : "min-w-80"}`}>
            <thead>
              {/* The head follows the two-line row of a phone: name left, material count right. */}
              <tr className="grid grid-cols-[minmax(0,1fr)_auto] border-b border-border-soft text-left text-xs text-muted uppercase sm:table-row">
                <th className="col-start-1 row-start-1 px-4 py-2">Workspace</th>
                {/* On a phone the long word would eat the module column, so it becomes its icon. */}
                <th className={`col-start-2 row-start-1 pl-2 pr-4 sm:pl-6 py-2 text-right ${manageColumns ? "sm:pr-4" : "sm:pr-1"}`}>
                  <span className="hidden sm:inline">{t("colSources")}</span>
                  <span className="sm:hidden inline-flex align-middle" title={t("colSources")}>
                    <Files size={14} weight="bold" />
                    <span className="sr-only">{t("colSources")}</span>
                  </span>
                </th>
                {manageColumns && (
                  <th className="hidden sm:table-cell pl-20 pr-4 py-2">
                    <span className="inline-flex items-center gap-1.5">
                      {t("colStatus")}
                      <HelpTooltip text={t("statusHelp")} />
                    </span>
                  </th>
                )}
                <th className={`hidden sm:table-cell pr-4 py-2 ${manageColumns ? "sm:pl-20" : "sm:pl-3"}`}></th>
              </tr>
            </thead>
            <tbody>
              {visibleModules.map((m) => (
                canManage(m.access) ? (
                  <WorkspaceTableRow
                    key={`${m.uuid}-${m.access}-${m.enrollment_id ?? "o"}`}
                    workspace={m}
                    onToggleActive={onToggleActive}
                    onToggleFavorite={onToggleFavorite}
                    onDelete={onDelete}
                    onEdit={onEdit}
                    onLinksChanged={onLinksChanged}
                    onRolesChanged={onRolesChanged}
                  />
                ) : (
                  <WorkspaceTableStudentRow
                    key={`${m.uuid}-${m.access}-${m.enrollment_id ?? "o"}`}
                    workspace={m}
                    onLeave={onLeaveDemo}
                    onToggleFavorite={onToggleFavorite}
                    manageColumns={manageColumns}
                  />
                )
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
              to: Math.min(startIdx + MODULES_PER_PAGE, sorted.length),
              total: sorted.length,
              label: "Workspaces",
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
