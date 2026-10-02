"use client";

import { useTranslations } from "next-intl";
import { CaretDown } from "@phosphor-icons/react";
import Band from "./Band";
import { SectionHeading } from "./InfoSections";

const GROUPS = [
  { key: "project", items: ["what", "how", "state"] },
  { key: "use", items: ["who", "account", "teachers", "device", "languages"] },
  { key: "francis", items: ["sources", "names", "material", "errors"] },
  { key: "data", items: ["dsgvo", "hosting", "expiry"] },
  { key: "outlook", items: ["after", "feedback"] },
] as const;

const ROW =
  "row-expandable flex items-baseline gap-4 py-3.5 text-base cursor-pointer list-none [&::-webkit-details-marker]:hidden";

/** Same register as the FAQ page, the group name stands in the margin on wide screens. */
export default function InfoFaq() {
  const t = useTranslations("eventInfo.faq");
  return (
    <Band tone="tint" testId="info-faq">
      <div className="grid grid-cols-1 @min-[64rem]:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] gap-8 @min-[64rem]:gap-16">
        <SectionHeading>{t("heading")}</SectionHeading>
        <div className="faq-list">
        {GROUPS.map((group) => (
          <div key={group.key} className="faq-group">
            <h3 className="faq-label">{t(`groups.${group.key}`)}</h3>
            <div>
              {group.items.map((item) => (
                <details key={item} name={group.key} className="faq-item group hover:bg-background">
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
      </div>
    </Band>
  );
}
