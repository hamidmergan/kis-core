import React from "react";
import { CaretRight } from "@phosphor-icons/react";
import { _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";

/** The path in the viewer header of mindmap and data table, the tool name leads back to the list. */
export function StudioViewerCrumbs({ toolKey, toolTitle, activeTitle, breadcrumbs, onToolClick }: {
  toolKey: string;
  toolTitle: string;
  activeTitle: string;
  breadcrumbs?: BreadcrumbItem[];
  onToolClick: () => void;
}) {
  if (!breadcrumbs) {
    return <span className="text-base font-bold flex-1 truncate" style={{ color: "var(--foreground)" }}>{activeTitle}</span>;
  }
  const badge = _getToolBadge(toolKey);
  return (
    <div className="flex items-center gap-1 text-sm min-w-0 flex-1">
      {breadcrumbs.map((b, i) => (
        <React.Fragment key={i}>
          <button type="button" onClick={b.onClick} className="font-medium shrink-0 text-muted hover:text-kb transition-colors">{b.label}</button>
          <CaretRight size={10} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
        </React.Fragment>
      ))}
      <button type="button" onClick={onToolClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={badge ? { color: badge.color } : {  }}>{toolTitle}</button>
      <CaretRight size={10} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
      <span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{activeTitle}</span>
    </div>
  );
}
