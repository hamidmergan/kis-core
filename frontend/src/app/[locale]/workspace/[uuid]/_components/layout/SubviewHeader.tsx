import React, { useContext } from "react";
import { useTranslations } from "next-intl";
import { CaretLeft, CaretRight, SidebarSimple } from "@phosphor-icons/react";
import { MinimizeContext } from "../../_context";

type BadgeStyle = { bg: string; color: string };

// Werte sind CSS-Variablen aus globals.css (Token-Block "Generisches Badge-Palette-System").
const LEARNING_TOOLS_BADGE: Record<string, BadgeStyle> = {
  Flashcards:   { bg: "var(--badge-emerald-bg)", color: "var(--badge-emerald-fg)" },
  Quiz:         { bg: "var(--badge-yellow-bg)",  color: "var(--badge-yellow-fg)" },
  DataTable:    { bg: "var(--badge-orange-bg)",  color: "var(--badge-orange-fg)" },
  Mindmap:      { bg: "var(--badge-teal-bg)",    color: "var(--badge-teal-fg)" },
  Infographic:  { bg: "var(--badge-violet-bg)",  color: "var(--badge-violet-fg)" },
  Presentation: { bg: "var(--badge-rose-bg)",    color: "var(--badge-rose-fg)" },
};
const LANGUAGE_TRAINING_BADGE: Record<string, BadgeStyle> = {
  Flashcards: { bg: "var(--badge-amber-bg)",   color: "var(--badge-amber-fg)" },
  Glossary:   { bg: "var(--badge-emerald-bg)", color: "var(--badge-emerald-fg)" },
  Cloze:      { bg: "var(--badge-rose-bg)",    color: "var(--badge-rose-fg)" },
  Grammar:    { bg: "var(--badge-violet-bg)",  color: "var(--badge-violet-fg)" },
  Listening:  { bg: "var(--badge-blue-bg)",    color: "var(--badge-blue-fg)" },
};
const SHARED_BADGE: Record<string, BadgeStyle> = {
  Notes:      { bg: "var(--badge-slate-bg)", color: "var(--badge-slate-fg)" },
  Statistics: { bg: "var(--badge-slate-bg)", color: "var(--badge-slate-fg)" },
};

export type ToolCategory = "learning_tools" | "language_training";
export type BreadcrumbItem = { label: string; onClick: () => void; toolKey?: string };

export function _getToolBadge(toolKey: string | undefined, category?: ToolCategory): BadgeStyle | null {
  if (!toolKey) return null;
  const map = category === "language_training" ? LANGUAGE_TRAINING_BADGE[toolKey] : LEARNING_TOOLS_BADGE[toolKey];
  return map ?? SHARED_BADGE[toolKey] ?? null;
}

export function SubviewHeader({ title, toolKey, onBack, breadcrumbs, rightContent, category }: { title: string; toolKey?: string; onBack: () => void; breadcrumbs?: BreadcrumbItem[]; rightContent?: React.ReactNode; category?: ToolCategory }) {
  const t = useTranslations("workspace.detail.panels");
  const minimize = useContext(MinimizeContext);
  const badge = _getToolBadge(toolKey, category);
  const mutedColor = "var(--muted)";
  const btnBg = "var(--surface-dim)";
  return (
    <div
      className="flex items-center gap-2 px-4 py-3 flex-shrink-0"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <button
        type="button"
        onClick={onBack}
        className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
        style={{ backgroundColor: btnBg, color: mutedColor }}
      >
        <CaretLeft size={13} />
      </button>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <div className="flex items-center gap-1 text-sm min-w-0 flex-1">
          {breadcrumbs.map((b, i) => {
            const bBadge = _getToolBadge(b.toolKey, category);
            return (
              <React.Fragment key={i}>
                {bBadge ? (
                  <button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={{ backgroundColor: bBadge.bg, color: bBadge.color }}>{b.label}</button>
                ) : (
                  <button type="button" onClick={b.onClick} className="font-medium shrink-0 opacity-60 hover:opacity-100 transition-opacity" style={{ color: mutedColor }}>{b.label}</button>
                )}
                <CaretRight size={10} weight="bold" style={{ color: mutedColor, opacity: 0.5 }} className="shrink-0" />
              </React.Fragment>
            );
          })}
          {badge ? (
            <span className="font-semibold truncate px-1.5 py-0.5 rounded" style={{ backgroundColor: badge.bg, color: badge.color }}>{title}</span>
          ) : (
            <span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{title}</span>
          )}
        </div>
      ) : (
        badge ? (
          <span className="text-sm font-semibold flex-1 inline-flex"><span className="px-1.5 py-0.5 rounded" style={{ backgroundColor: badge.bg, color: badge.color }}>{title}</span></span>
        ) : (
          <span className="text-sm font-semibold flex-1" style={{ color: "var(--foreground)" }}>{title}</span>
        )
      )}
      {rightContent}
      {minimize && (
        <button type="button" onClick={minimize}
          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon ml-auto"
          style={{ backgroundColor: "var(--surface-dim)" }}
          title={t("minimize")}>
          <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
        </button>
      )}
    </div>
  );
}
