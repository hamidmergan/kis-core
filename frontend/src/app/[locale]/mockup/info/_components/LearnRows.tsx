"use client";

import { useTranslations } from "next-intl";
import Band from "./Band";
import { SectionHeading } from "./InfoSections";
import Screenshot from "./Screenshot";

const ROWS = [
  { key: "material", image: "video" },
  { key: "sources", image: "citation" },
  { key: "practice", image: "quiz" },
  { key: "overview", image: "mindmap" },
] as const;

/** What learning with Francis looks like, one real screenshot per idea, image and text alternate sides. */
export default function LearnRows() {
  const t = useTranslations("mockup.info.learn");
  return (
    <Band tone="tint" testId="info-learn">
      <div className="flex flex-col gap-8 @min-[64rem]:gap-12">
        <div className="max-w-3xl flex flex-col gap-4">
          <SectionHeading>{t("heading")}</SectionHeading>
          <p className="text-lg @min-[40rem]:text-xl leading-relaxed text-foreground-soft text-balance">{t("intro")}</p>
        </div>
        <div className="flex flex-col gap-14 @min-[64rem]:gap-24">
        {ROWS.map(({ key, image }, i) => (
          <div key={key} className="grid grid-cols-1 @min-[64rem]:grid-cols-12 gap-8 @min-[64rem]:gap-16 items-center" data-testid="learn-row">
            <Screenshot name={image} alt={t(`rows.${key}.alt`)} className={`@min-[64rem]:col-span-8 ${i % 2 ? "@min-[64rem]:order-2" : ""}`} />
            <div className={`@min-[64rem]:col-span-4 flex flex-col gap-4 ${i % 2 ? "@min-[64rem]:order-1" : ""}`}>
              <h3 className="text-2xl @min-[40rem]:text-3xl font-semibold tracking-[-0.02em] leading-tight">{t(`rows.${key}.title`)}</h3>
              <p className="text-lg leading-relaxed text-foreground-soft">{t(`rows.${key}.body`)}</p>
            </div>
          </div>
        ))}
        </div>
      </div>
    </Band>
  );
}
