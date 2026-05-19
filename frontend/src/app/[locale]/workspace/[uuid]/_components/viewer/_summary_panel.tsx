import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";

type SummaryPanelProps = {
  page: number;
  summaryText: string | undefined;
  summariesStatus: string;
  onGenerate: () => void | Promise<void>;
  onScrollPdf?: (deltaY: number) => void;
};

export function SummaryPanel({
  page, summaryText, summariesStatus, onGenerate, onScrollPdf,
}: SummaryPanelProps) {
  const t = useTranslations("workspace.detail.summary");
  const contentRef = useRef<HTMLDivElement>(null);

  // Forward wheel events to the PDF when the panel can't scroll further in that direction.
  // Lets the user scroll the PDF naturally even with the cursor over the summary.
  useEffect(() => {
    const el = contentRef.current;
    if (!el || !onScrollPdf) return;
    const handler = (e: WheelEvent) => {
      const canScrollDown = el.scrollHeight - el.clientHeight - el.scrollTop > 1;
      const canScrollUp = el.scrollTop > 0;
      const goingDown = e.deltaY > 0;
      if ((goingDown && !canScrollDown) || (!goingDown && !canScrollUp)) {
        e.preventDefault();
        onScrollPdf(e.deltaY);
      }
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [onScrollPdf]);

  const renderContent = () => {
    if (summariesStatus === "generating" && !summaryText) {
      return <span style={{ color: "var(--color-fg-muted, #9ca3af)" }}>{t("generating")}</span>;
    }
    if (summaryText) {
      return renderWithBreaks(summaryText);
    }
    if (summariesStatus === "none" || summariesStatus === "failed" || summariesStatus === "rate_limited") {
      return (
        <div style={{ textAlign: "center", padding: "16px 12px" }}>
          <span style={{ color: "var(--muted)", display: "block", marginBottom: 10, fontSize: 12 }}>
            {summariesStatus === "rate_limited" ? t("rateLimited")
              : summariesStatus === "failed" ? t("failed")
              : t("none")}
          </span>
          <button
            onClick={() => { void onGenerate(); }}
            style={{ padding: "6px 16px", fontSize: 12, borderRadius: 6, border: "1px solid var(--color-accent, #3b82f6)", background: "var(--color-accent, #3b82f6)", color: "var(--color-accent-fg, #fff)", cursor: "pointer", fontWeight: 500 }}
          >
            {t("generateButton")}
          </button>
        </div>
      );
    }
    return <span style={{ color: "var(--color-fg-muted, #9ca3af)" }}>{t("noneForPage")}</span>;
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: "inherit", userSelect: "text", WebkitUserSelect: "text", cursor: "text" }}>
      <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--color-border-default, var(--border-soft))", fontWeight: 600, fontSize: 12, color: "var(--color-fg-primary, #1f2937)" }}>
        {t("header", { page })}
      </div>
      <div ref={contentRef} style={{ flex: 1, overflowY: "auto", padding: 12, fontSize: 12, lineHeight: 1.6, color: "var(--color-fg-primary, #1f2937)" }}>
        {renderContent()}
      </div>
    </div>
  );
}

function renderWithBreaks(text: string) {
  const parts = text.split("\n");
  return parts.map((p, i) => (
    <span key={i}>
      {p}
      {i < parts.length - 1 ? <br /> : null}
    </span>
  ));
}
