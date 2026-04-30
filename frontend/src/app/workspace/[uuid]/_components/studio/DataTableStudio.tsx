import React, { useContext, useEffect, useState } from "react";
import { CaretLeft, CaretRight, FilePdf, Files, SidebarSimple, Sparkle, Table, Trash } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { DataTableData, DataTableRowSource, DataTableSource, Source, StudentStats } from "../../_types";
import { _getChipIcon, _isMediaFile, _sourceChipKey } from "../../_utils";
import { MinimizeContext } from "../../_context";
import { SubviewHeader, _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";

export function DataTableStudio({
  table, sources, loading, onGenerate, onBack,
  savedList, onSelect, onDelete, sourceCount,
  allSources, onPillClick, stats, breadcrumbs,
  openInViewer, onViewerOpened,
}: {
  table: DataTableData | null;
  sources: DataTableSource[];
  loading: boolean;
  onGenerate: () => void;
  onBack: () => void;
  savedList: { id: number; title: string; created_at: string | null }[];
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  sourceCount: number;
  allSources?: Source[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  stats?: StudentStats | null;
  breadcrumbs?: BreadcrumbItem[];
  openInViewer?: boolean;
  onViewerOpened?: () => void;
}) {
  const [view, setView] = useState<"viewer" | "list">(openInViewer ? "viewer" : "list");
  const minimize = useContext(MinimizeContext);

  useEffect(() => {
    if (openInViewer) {
      setView("viewer");
      onViewerOpened?.();
    }
  }, [openInViewer, onViewerOpened]);
  const noSources = sourceCount === 0;
  const atLimit = savedList.length >= 20;
  const activeTitle = table?.title || "Datentabelle";

  return (
    <div className="flex flex-col h-full">
      {/* ── List view ── */}
      <div style={{ display: view === "list" ? "flex" : "none" }} className="flex-col h-full">
        <SubviewHeader title="Datentabelle" toolKey="DataTable" onBack={onBack} breadcrumbs={breadcrumbs} />
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="rounded-xl px-3 py-2 text-sm font-medium flex items-center gap-2"
            style={{
              color: noSources ? "var(--error-strong)" : sourceCount > 5 ? "#c4820e" : "var(--kb)",
            }}>
            <Files size={13} weight="bold" />
            {noSources
              ? "Keine Quelle ausgewählt"
              : sourceCount === 1
                ? "1 Quelle ausgewählt"
                : sourceCount <= 5
                  ? `${sourceCount} Quellen ausgewählt`
                  : `${sourceCount} Quellen vorhanden, es werden maximal 5 berücksichtigt`}
          </div>

          {savedList.length === 0 && !loading ? (
            <EmptyState
              className="pt-[15%]"
              size="lg"
              icon={<Table size={48} weight="bold" />}
              text="Wähle Quellen aus und drücke auf Erstellen."
              action={
                <button type="button" onClick={() => onGenerate()}
                  disabled={noSources || loading || atLimit}
                  className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                  <Sparkle size={12} weight="bold" /> Erstellen ({savedList.length}/20)
                </button>
              }
            />
          ) : (
            <>
              <div className="flex justify-center">
                <button type="button" onClick={() => onGenerate()}
                  disabled={noSources || loading || atLimit}
                  className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                  <Sparkle size={12} weight="bold" /> Erstellen ({savedList.length}/20)
                </button>
              </div>
              <div className="flex items-center justify-between px-1">
                <span className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>{savedList.length} {savedList.length === 1 ? "Datentabelle" : "Datentabellen"}</span>
              </div>
              <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
                {loading && (
                  <div className="bg-white rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden opacity-70"
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Spinner size="sm" />
                      <span className="text-sm font-semibold leading-snug flex-1 line-clamp-2" style={{ color: "var(--foreground)" }}>Wird generiert…</span>
                    </div>
                  </div>
                )}
                {savedList.map((item) => (
                  <div key={item.id}
                    onClick={() => { onSelect(item.id); setView("viewer"); }}
                    className="bg-white rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden group cursor-pointer hover:outline-2 hover:outline-[var(--kb)] -outline-offset-2 transition"
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Table size={16} weight="duotone" style={{ color: "var(--kb)", flexShrink: 0 }} />
                      <span className="text-sm font-semibold leading-snug flex-1 line-clamp-3 kis-tooltip" style={{ color: "var(--foreground)" }} data-tip={item.title}>
                        {item.title}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-auto pt-1">
                      <span className="text-xs font-medium" >
                        {item.created_at ? new Date(item.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                      </span>
                      <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
                        className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                        style={{ backgroundColor: "var(--surface-dim)" }}>
                        <Trash size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Viewer ── */}
      <div style={{ display: view === "viewer" ? "flex" : "none" }} className="flex-col h-full">
        <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <button type="button" onClick={() => setView("list")}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}>
            <CaretLeft size={13} />
          </button>
          {breadcrumbs ? (() => {
            const badge = _getToolBadge("DataTable");
            return (
              <div className="flex items-center gap-1 text-sm min-w-0 flex-1">
                {breadcrumbs.map((b, i) => (
                  <React.Fragment key={i}>
                    <button type="button" onClick={b.onClick} className="font-medium shrink-0 transition-colors"  onMouseEnter={(e) => e.currentTarget.style.color = "var(--kb)"} onMouseLeave={(e) => e.currentTarget.style.color = "var(--muted)"}>{b.label}</button>
                    <CaretRight size={10} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
                  </React.Fragment>
                ))}
                <button type="button" onClick={() => setView("list")} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={badge ? { backgroundColor: badge.bg, color: badge.color } : {  }}>Datentabelle</button>
                <CaretRight size={10} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
                <span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{activeTitle}</span>
              </div>
            );
          })() : (<span className="text-base font-bold flex-1 truncate" style={{ color: "var(--foreground)" }}>{activeTitle}</span>)}
          {minimize && (
            <button type="button" onClick={minimize} title="Panel minimieren"
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
                <p className="text-sm" >Datentabelle wird generiert…</p>
              </div>
            </div>
          )}
          {table && (
            <div className="w-full px-4 pt-4 pb-6 flex flex-col gap-4" style={{ userSelect: "text" }}>
              <p className="text-xs" >
                Basierend auf {sources.length} Quelle{sources.length !== 1 ? "n" : ""}
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
                        Quelle
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
                                  const isMedia = _isMediaFile(rs.source_label);
                                  let startTime: number | undefined;
                                  let pageNum = 0;
                                  if (isMedia && typeof rs.page === "string") {
                                    const parts = rs.page.split(":").map(Number);
                                    if (parts.length === 3) startTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
                                    else if (parts.length === 2) startTime = parts[0] * 60 + parts[1];
                                  } else {
                                    pageNum = typeof rs.page === "number" ? rs.page : parseInt(String(rs.page), 10) || 0;
                                  }
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
                                let pageNum = 0;
                                let startTime: number | undefined;
                                const label = isMedia ? String(rs.page) : `S. ${rs.page}`;
                                if (isMedia && typeof rs.page === "string") {
                                  const parts = rs.page.split(":").map(Number);
                                  if (parts.length === 3) startTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
                                  else if (parts.length === 2) startTime = parts[0] * 60 + parts[1];
                                } else {
                                  pageNum = typeof rs.page === "number" ? rs.page : parseInt(String(rs.page), 10) || 0;
                                }
                                const sourceNum = sources.find((sl) => sl.filename === rs.source_label)?.number ?? (si + 1);
                                return (
                                  <span key={si} role="button" tabIndex={0}
                                    onClick={() => src && onPillClick?.(src.uuid, pageNum, src.filename, rs.highlight, startTime)}
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

              {sources.length > 0 && (
                <div className="flex flex-col gap-1 pt-2">
                  {sources.map((s) => (
                    <p key={s.number} className="text-xs leading-snug text-[var(--muted)]">
                      [{s.number}] {s.filename}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
