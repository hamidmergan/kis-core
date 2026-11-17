import { useContext, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretLeft, FilePdf, SidebarSimple, Table } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { DataTableData, DataTableRowSource, DataTableSource, Source } from "../../_types";
import { _getChipIcon, _isMediaFile, _sourceChipKey } from "../../_utils";
import { MinimizeContext } from "../../_context";
import type { BreadcrumbItem } from "../layout/SubviewHeader";
import { StudioSourceLegend } from "./StudioSourceLegend";
import { InstructionNote } from "./InstructionField";
import { StudioSavedList } from "./StudioSavedList";
import { StudioViewerCrumbs } from "./StudioViewerCrumbs";
import { pageNumberOf, timeLabelSeconds } from "./_sourceRefs";

// Where a row source points: a time for media, a page for everything else.
function rowSourceTarget(rs: DataTableRowSource): { pageNum: number; startTime: number | undefined } {
  if (_isMediaFile(rs.source_label) && typeof rs.page === "string") {
    return { pageNum: 0, startTime: timeLabelSeconds(rs.page) };
  }
  return { pageNum: pageNumberOf(rs.page), startTime: undefined };
}

export function DataTableStudio({
  table, sources, loading, onGenerate, onBack,
  savedList, onSelect, onDelete, onRename, sourceCount,
  allSources, onPillClick, breadcrumbs,
  openInViewer, onViewerOpened, instruction, instructionUnmatched,
}: {
  table: DataTableData | null;
  sources: DataTableSource[];
  loading: boolean;
  onGenerate: (instruction: string) => void;
  onBack: () => void;
  savedList: { id: number; title: string; created_at: string | null; user_instruction?: string }[];
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  onRename?: (id: number, title: string) => Promise<void>;
  sourceCount: number;
  allSources?: Source[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  breadcrumbs?: BreadcrumbItem[];
  openInViewer?: boolean;
  onViewerOpened?: () => void;
  /** The instruction the shown table was made with, and whether the sources had nothing on it. */
  instruction?: string;
  instructionUnmatched?: boolean;
}) {
  const t = useTranslations("workspace.detail.studio");
  const tDt = useTranslations("workspace.detail.studio.dataTable");
  const [view, setView] = useState<"viewer" | "list">(openInViewer ? "viewer" : "list");
  const minimize = useContext(MinimizeContext);

  useEffect(() => {
    if (openInViewer) {
      setView("viewer");
      onViewerOpened?.();
    }
  }, [openInViewer, onViewerOpened]);
  const activeTitle = table?.title || tDt("fallbackTitle");

  return (
    <div className="flex flex-col h-full">
      {/* ── List view ── */}
      <div style={{ display: view === "list" ? "flex" : "none" }} className="flex-col h-full">
        <StudioSavedList
          toolKey="DataTable" modalId="table-instruction" icon={Table}
          labels={{ title: tDt("title"), emptyHint: tDt("emptyHint"), countOne: tDt("countOne"), countMany: tDt("countMany") }}
          items={savedList} loading={loading} sourceCount={sourceCount} breadcrumbs={breadcrumbs}
          onBack={onBack} onGenerate={onGenerate}
          onOpen={(id) => { onSelect(id); setView("viewer"); }}
          onDelete={onDelete} onRename={onRename}
        />
      </div>

      {/* ── Viewer ── */}
      <div style={{ display: view === "viewer" ? "flex" : "none" }} className="flex-col h-full">
        <div data-panel-header="" className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <button type="button" onClick={() => setView("list")}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}>
            <CaretLeft size={13} />
          </button>
          <StudioViewerCrumbs toolKey="DataTable" toolTitle={tDt("title")} activeTitle={activeTitle} breadcrumbs={breadcrumbs}
            onToolClick={() => setView("list")} />
          {minimize && (
            <button type="button" onClick={minimize} title={t("minimizePanel")}
              className="w-7 h-7 flex items-center justify-center rounded-full btn-icon ml-auto"
              style={{ backgroundColor: "var(--surface-dim)" }}>
              <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto">
          {!table && loading && (
            <div className="flex-1 flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-3">
                <Spinner size="lg" />
                <p className="text-sm" >{tDt("loadingViewer")}</p>
              </div>
            </div>
          )}
          {table && (
            <div className="w-full px-4 pt-4 pb-6 flex flex-col gap-4" style={{ userSelect: "text" }}>
              <InstructionNote instruction={instruction} unmatched={instructionUnmatched}
                shownText={t("generate.instructionShown", { text: instruction || "" })}
                unmatchedText={t("generate.instructionUnmatched")} />
              <p className="text-xs" >
                {tDt("basedOn", { n: sources.length })}
              </p>

              {(() => {
                const sourceColKeywords = ["quelle", "quellen", "source", "sources", "quellenangabe"];
                const visibleColIndices = table.columns.map((col, i) => ({ col, i })).filter(({ col }) => !sourceColKeywords.includes(col.trim().toLowerCase()));
                return (
              <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid var(--border)" }}>
                <table className="w-full border-collapse text-sm" style={{ minWidth: 500 }}>
                  <thead>
                    <tr>
                      {visibleColIndices.map(({ col, i }) => (
                        <th key={i}
                          className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap"
                          style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)", borderBottom: "1px solid var(--border)" }}>
                          {col}
                        </th>
                      ))}
                      <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap"
                        style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)", borderBottom: "1px solid var(--border)" }}>
                        {tDt("sourceCol")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.rows.map((row, ri) => (
                      <tr key={ri} style={{ backgroundColor: ri % 2 === 0 ? "var(--background)" : "var(--surface)" }}>
                        {visibleColIndices.map(({ i: ci }) => (
                          <td key={ci} className="px-3 py-2 align-top leading-snug"
                            style={{ borderBottom: "1px solid var(--border)", color: "var(--foreground)" }}>
                            {row.cells[ci]}
                          </td>
                        ))}
                        <td className="px-3 py-2 align-top"
                          style={{ borderBottom: "1px solid var(--border)" }}>
                          <div className="flex flex-wrap gap-1">
                            {(() => {
                              const seenKeys = new Set<string>();
                              return row.sources.filter((s) => {
                                if (typeof s === "object" && s !== null && "source_label" in s) {
                                  const rs = s as DataTableRowSource;
                                  const { pageNum, startTime } = rowSourceTarget(rs);
                                  const k = _sourceChipKey(rs.source_label, pageNum, startTime, rs.highlight);
                                  if (seenKeys.has(k)) return false;
                                  seenKeys.add(k);
                                  return true;
                                }
                                const k = `legacy:${s as number}`;
                                if (seenKeys.has(k)) return false;
                                seenKeys.add(k);
                                return true;
                              });
                            })().map((s, si) => {
                              if (typeof s === "object" && s !== null && "source_label" in s) {
                                const rs = s as DataTableRowSource;
                                const src = allSources?.find((a) => a.filename === rs.source_label);
                                const isMedia = _isMediaFile(rs.source_label);
                                const SourceIcon = _getChipIcon(rs.source_label);
                                const { pageNum, startTime } = rowSourceTarget(rs);
                                const label = isMedia ? String(rs.page) : tDt("pageLabel", { page: rs.page });
                                const sourceNum = sources.find((sl) => sl.filename === rs.source_label)?.number ?? (si + 1);
                                return (
                                  <span key={si} role="button" tabIndex={0}
                                    onClick={() => src && onPillClick?.(src.uuid, pageNum, src.filename, [rs.highlight, ...row.cells].filter(Boolean).join(" "), startTime)}
                                    onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
                                    className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full font-medium chip-cite whitespace-nowrap cursor-pointer"
                                    style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}>
                                    <SourceIcon size={10} weight="bold" />
                                    [{sourceNum}] {label}
                                  </span>
                                );
                              }
                              const num = s as number;
                              const legend = sources.find((src) => src.number === num);
                              const fname = legend?.filename || "";
                              const src = legend ? allSources?.find((a) => a.filename === fname) : undefined;
                              const LegacyIcon = fname ? _getChipIcon(fname) : FilePdf;
                              return (
                                <span key={si} role="button" tabIndex={0}
                                  onClick={() => src && onPillClick?.(src.uuid, 0, src.filename)}
                                  onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.click(); }}
                                  className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full font-medium chip-cite whitespace-nowrap cursor-pointer"
                                  style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}>
                                  <LegacyIcon size={10} weight="bold" />
                                  [{num}]
                                </span>
                              );
                            })}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
                );
              })()}

              {sources.length > 0 && (() => {
                // A number nobody finds in the table only confuses, so say it plainly.
                const benutzt = new Set(
                  (table.rows || []).flatMap((r) => (r.sources || [])
                    .map((x) => (typeof x === "number" ? sources.find((s) => s.number === x)?.filename : x.source_label))
                    .filter((n): n is string => !!n)));
                return (
                <StudioSourceLegend count={sources.length} className="pt-2">
                  {sources.map((s) => (
                    <p key={s.number}
                       className={`text-xs leading-snug pl-4 text-[var(--muted)]${benutzt.has(s.filename) ? "" : " opacity-60"}`}>
                      [{s.number}] {s.filename}
                    </p>
                  ))}
                </StudioSourceLegend>
                );
              })()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
