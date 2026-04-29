"use client";

import { useState } from "react";
import HelpTooltip from "@/components/ui/HelpTooltip";
import ModuleTableRow from "./ModuleTableRow";
import type { AccessLink, KiTutorModule } from "../_shared";

const MODULES_PER_PAGE = 20;

interface ModuleTableProps {
  modules: KiTutorModule[];
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}

export default function ModuleTable({
  modules,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: ModuleTableProps) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(modules.length / MODULES_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * MODULES_PER_PAGE;
  const visibleModules = modules.slice(startIdx, startIdx + MODULES_PER_PAGE);

  return (
    <>
      <div className="w-full overflow-x-auto">
        <table className="w-full" style={{ tableLayout: "fixed", minWidth: "760px" }}>
          <colgroup>
            <col style={{ width: "44px" }} />
            <col />
            <col style={{ width: "100px" }} />
            <col style={{ width: "100px" }} />
            <col style={{ width: "140px" }} />
            <col style={{ width: "52px" }} />
            <col style={{ width: "44px" }} />
          </colgroup>
          <thead>
            <tr>
              <th className="pb-3"></th>
              <th className="text-left pr-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Workspace</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Quellen</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Links</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>
                <span className="inline-flex items-center gap-1.5">
                  Status
                  <HelpTooltip text="Aktiv: Studierende können sich über Zugangslinks in den Workspace einschreiben und die Inhalte nutzen. Inaktiv: Der Workspace ist für Studierende gesperrt. Bestehende Einschreibungen bleiben erhalten." />
                </span>
              </th>
              <th className="pb-3"></th>
              <th className="pr-2 pb-3"></th>
            </tr>
          </thead>
          <tbody>
            {visibleModules.map((m) => (
              <ModuleTableRow
                key={m.uuid}
                module={m}
                onToggleActive={onToggleActive}
                onDelete={onDelete}
                onEdit={onEdit}
                onLinksChanged={onLinksChanged}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            Zeige {startIdx + 1} bis {Math.min(startIdx + MODULES_PER_PAGE, modules.length)} von {modules.length} Workspaces
          </p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage(safePage - 1)}
              disabled={safePage === 1}
              className="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-[var(--foreground)] enabled:hover:outline-2 enabled:hover:outline-[var(--kb)] enabled:hover:text-[var(--kb)] -outline-offset-1"
            >
              Zurück
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
              Weiter
            </button>
          </div>
        </div>
      )}
    </>
  );
}
