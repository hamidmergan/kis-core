import React, { useContext } from "react";
import { CaretLeft, CaretRight, SidebarSimple } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { MinimizeContext } from "../../_context";
import { _getToolBadge, type BreadcrumbItem, type ToolCategory } from "../layout/SubviewHeader";
import { setDisplayTitle } from "./_setTitle";

/** The header of a running exercise: back, the path, the set name, minimize. */
export function ExerciseHeader({ title, breadcrumbs, badgeCategory, onBack }: {
  title: string;
  breadcrumbs?: BreadcrumbItem[];
  badgeCategory: ToolCategory;
  onBack: () => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const minimize = useContext(MinimizeContext);
  const shownTitle = setDisplayTitle(title);
  return (
    <div data-panel-header="" className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
      <button type="button" onClick={onBack}
        className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
        style={{ backgroundColor: "var(--surface-dim)" }}>
        <CaretLeft size={13} />
      </button>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <div className="flex items-center gap-1 text-xs min-w-0 flex-1">
          {breadcrumbs.map((b, i) => {
            const bBadge = _getToolBadge(b.toolKey, badgeCategory);
            return (
              <React.Fragment key={i}>
                {bBadge ? (
                  <button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={{ color: bBadge.color }}>{b.label}</button>
                ) : (
                  <button type="button" onClick={b.onClick} className="font-medium shrink-0 opacity-60 hover:opacity-100 transition-opacity" style={{ color: "var(--muted)" }}>{b.label}</button>
                )}
                <CaretRight size={9} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
              </React.Fragment>
            );
          })}
          <span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{shownTitle}</span>
        </div>
      ) : (
        <span className="text-xs font-semibold flex-1 truncate" style={{ color: "var(--foreground)" }}>{shownTitle}</span>
      )}
      {minimize && (
        <button type="button" onClick={minimize}
          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }}
          title={t("common.minimizePanel")}>
          <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
        </button>
      )}
    </div>
  );
}
