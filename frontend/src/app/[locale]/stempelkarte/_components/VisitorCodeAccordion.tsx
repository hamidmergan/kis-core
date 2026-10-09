"use client";

import { useTranslations } from "next-intl";
import { CaretRight } from "@phosphor-icons/react";

const ROW =
  "row-expandable flex items-center gap-2 py-3.5 text-base cursor-pointer list-none [&::-webkit-details-marker]:hidden";

/** Same expand-row register as the FAQ, caret on the left like a disclosure triangle: one row that reveals the visitor's own code for a targeted reset at a stand. */
export default function VisitorCodeAccordion({ code }: { code: string }) {
  const t = useTranslations("eventStamp.myCode");
  if (!code) return null;
  return (
    <details className="faq-item group" data-testid="visitor-code-accordion">
      <summary className={ROW}>
        <span className="row-caret shrink-0 transition-colors" aria-hidden="true">
          <CaretRight size={14} weight="bold" className="transition-transform group-open:rotate-90" />
        </span>
        <span className="font-medium text-foreground-soft">{t("reveal")}</span>
      </summary>
      <p className="pb-4 text-sm leading-relaxed text-foreground-soft">
        {t("hint")}{" "}
        <span className="font-mono font-semibold text-foreground tracking-wider">
          {code.slice(0, 3)}-{code.slice(3)}
        </span>
      </p>
    </details>
  );
}
