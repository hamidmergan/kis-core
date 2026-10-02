"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { BookOpenText, Quotes, WarningCircle, type Icon } from "@phosphor-icons/react";
import Band from "./Band";

/** Shared section heading, large on wide screens. */
export function SectionHeading({ children }: { children: ReactNode }) {
  return <h2 className="text-3xl @min-[40rem]:text-4xl font-semibold tracking-[-0.02em] leading-tight">{children}</h2>;
}

const PURPOSE_KEYS = ["students", "pilot", "funding", "scope"] as const;

export function PurposeSection() {
  const t = useTranslations("mockup.info.purpose");
  return (
    <Band testId="info-purpose">
      <div className="grid grid-cols-1 @min-[64rem]:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] gap-8 @min-[64rem]:gap-16">
        <SectionHeading>{t("heading")}</SectionHeading>
        <ul className="grid grid-cols-1 @min-[40rem]:grid-cols-2 gap-x-10 gap-y-8">
          {PURPOSE_KEYS.map((key) => (
            <li key={key} className="border-l-4 border-kb pl-5 text-lg @min-[40rem]:text-xl leading-relaxed text-foreground-soft">
              {t(key)}
            </li>
          ))}
        </ul>
      </div>
    </Band>
  );
}

const HANDLING: Array<{ key: "sources" | "names" | "errors"; icon: Icon }> = [
  { key: "sources", icon: BookOpenText },
  { key: "names", icon: Quotes },
  { key: "errors", icon: WarningCircle },
];

export function HandlingSection() {
  const t = useTranslations("mockup.info.handling");
  return (
    <Band tone="tint" testId="info-handling">
      <div className="flex flex-col gap-10">
        <SectionHeading>{t("heading")}</SectionHeading>
        <ul className="grid grid-cols-1 @min-[48rem]:grid-cols-3 gap-6">
          {HANDLING.map(({ key, icon: Icon }) => (
            <li key={key} className="flex flex-col gap-4 rounded-2xl border-2 border-border-soft bg-background p-6 @min-[40rem]:p-8">
              <span className="flex items-center justify-center w-12 h-12 rounded-full bg-kb/10 text-kb-dark">
                <Icon size={26} weight="bold" aria-hidden="true" />
              </span>
              <p className="text-lg leading-relaxed text-foreground-soft">{t(key)}</p>
            </li>
          ))}
        </ul>
      </div>
    </Band>
  );
}

export function TeamSection() {
  const t = useTranslations("mockup.info.team");
  return (
    <Band testId="info-team">
      <div className="grid grid-cols-1 @min-[64rem]:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] gap-8 @min-[64rem]:gap-16">
        <SectionHeading>{t("heading")}</SectionHeading>
        <div className="flex flex-col gap-6">
          <p className="text-lg @min-[40rem]:text-xl leading-relaxed text-foreground-soft max-w-prose">{t("body")}</p>
          <div className="self-start rounded-md border-2 border-dashed border-border px-4 py-2 text-sm text-muted">
            {t("contact")}
          </div>
        </div>
      </div>
    </Band>
  );
}
