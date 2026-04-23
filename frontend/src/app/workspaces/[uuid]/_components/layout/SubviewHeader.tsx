import React, { useContext } from "react";
import { CaretLeft, CaretRight, SidebarSimple } from "@phosphor-icons/react";
import { MinimizeContext } from "../../_context";

// Lerntools: var(--kb) blue tones
const LERNTOOLS_BADGE: Record<string, { bg: string; color: string }> = {
  Karteikarten: { bg: "rgba(220,252,231,0.7)", color: "#166534" },
  Quiz: { bg: "rgba(254,249,195,0.7)", color: "#A16207" },
  Datentabelle: { bg: "rgba(255,237,213,0.7)", color: "#C2410C" },
  Mindmap: { bg: "rgba(236,254,255,0.7)", color: "#0E7490" },
  Infografik: { bg: "rgba(237,233,254,0.7)", color: "#534AB7" },
  "Präsentation": { bg: "rgba(255,228,230,0.7)", color: "#BE123C" },
};
// Sprachtraining: distinct tool colors (each unique)
const SPRACHTRAINING_BADGE: Record<string, { bg: string; color: string }> = {
  Lernkarten: { bg: "rgba(245,235,220,0.7)", color: "#78350F" },
  Glossar: { bg: "rgba(220,252,231,0.7)", color: "#166534" },
  "Lückentext": { bg: "rgba(255,228,230,0.7)", color: "#BE123C" },
  "Begriffe-Quiz": { bg: "rgba(237,233,254,0.7)", color: "#534AB7" },
};
const SHARED_BADGE: Record<string, { bg: string; color: string }> = {
  Notizen: { bg: "rgba(241,245,249,0.7)", color: "#475569" },
  Statistik: { bg: "rgba(241,245,249,0.7)", color: "#475569" },
};

export function _getToolBadge(title: string, category?: "lerntools" | "sprachtraining"): { bg: string; color: string } | null {
  const map = category === "sprachtraining" ? SPRACHTRAINING_BADGE[title] : LERNTOOLS_BADGE[title];
  return map ?? SHARED_BADGE[title] ?? null;
}

export function SubviewHeader({ title, onBack, breadcrumbs, rightContent, category }: { title: string; onBack: () => void; breadcrumbs?: { label: string; onClick: () => void }[]; rightContent?: React.ReactNode; category?: "lerntools" | "sprachtraining" }) {
  const minimize = useContext(MinimizeContext);
  const badge = _getToolBadge(title, category);
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
        className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
        style={{ backgroundColor: btnBg, color: mutedColor }}
      >
        <CaretLeft size={13} />
      </button>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <div className="flex items-center gap-1 text-sm min-w-0 flex-1">
          {breadcrumbs.map((b, i) => {
            const bBadge = _getToolBadge(b.label, category);
            return (
              <React.Fragment key={i}>
                {bBadge ? (
                  <button type="button" onClick={b.onClick} className="font-medium shrink-0 px-1.5 py-0.5 rounded transition-opacity hover:opacity-80" style={{ backgroundColor: bBadge.bg, color: bBadge.color }}>{b.label}</button>
                ) : (
                  <button type="button" onClick={b.onClick} className="font-medium shrink-0 transition-colors" style={{ color: mutedColor }} onMouseEnter={(e) => e.currentTarget.style.color = "var(--kb)"} onMouseLeave={(e) => e.currentTarget.style.color = mutedColor}>{b.label}</button>
                )}
                <CaretRight size={10} weight="bold" style={{ color: mutedColor, opacity: 0.5 }} className="shrink-0" />
              </React.Fragment>
            );
          })}
          {badge ? (
            <span className="font-semibold truncate px-1.5 py-0.5 rounded" style={{ backgroundColor: badge.bg, color: badge.color }}>{title}</span>
          ) : (
            <span className="font-semibold truncate" style={{ color: "var(--text)" }}>{title}</span>
          )}
        </div>
      ) : (
        badge ? (
          <span className="text-sm font-semibold flex-1 inline-flex"><span className="px-1.5 py-0.5 rounded" style={{ backgroundColor: badge.bg, color: badge.color }}>{title}</span></span>
        ) : (
          <span className="text-sm font-semibold flex-1" style={{ color: "var(--text)" }}>{title}</span>
        )
      )}
      {rightContent}
      {minimize && (
        <button type="button" onClick={minimize}
          className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity ml-auto"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
          title="Panel minimieren">
          <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
        </button>
      )}
    </div>
  );
}
