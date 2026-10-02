"use client";

import { useTranslations } from "next-intl";
import { CaretDown } from "@phosphor-icons/react";
import { Section } from "./InfoSections";

const GROUPS = [
  { key: "use", items: ["who", "account", "cost"] },
  { key: "outlook", items: ["data", "after"] },
] as const;

const ROW =
  "row-expandable flex items-baseline gap-4 py-3.5 text-base cursor-pointer list-none [&::-webkit-details-marker]:hidden";

/** Same register as the FAQ page, the group name stands in the margin on wide screens. */
export default function InfoFaq() {
  const t = useTranslations("mockup.info.faq");
  return (
    <Section heading={t("heading")} testId="info-faq">
      <div className="faq-list">
        {GROUPS.map((group) => (
          <div key={group.key} className="faq-group">
            <h3 className="faq-label">{t(`groups.${group.key}`)}</h3>
            <div>
              {group.items.map((item) => (
                <details key={item} name={group.key} className="faq-item group">
                  <summary className={ROW}>
                    <span className="faq-q">{t(`items.${item}.q`)}</span>
                    <span className="row-caret shrink-0 transition-colors" aria-hidden="true">
                      <CaretDown size={14} weight="bold" className="transition-transform group-open:rotate-180" />
                    </span>
                  </summary>
                  <p className="pb-4 text-sm leading-relaxed text-foreground-soft max-w-[62ch]">
                    {t(`items.${item}.a`)}
                  </p>
                </details>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
