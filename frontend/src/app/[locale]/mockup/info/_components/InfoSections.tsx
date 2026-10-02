"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { BookOpenText, Quotes, WarningCircle, type Icon } from "@phosphor-icons/react";
import ScreenshotSlot from "./ScreenshotSlot";

/** One page section with the shared heading size. */
export function Section({ heading, children, testId }: { heading: string; children: ReactNode; testId: string }) {
  return (
    <section className="flex flex-col gap-5" data-testid={testId}>
      <h2 className="text-xl font-semibold tracking-[-0.01em] text-foreground">{heading}</h2>
      {children}
    </section>
  );
}

const PURPOSE_KEYS = ["students", "pilot", "funding", "scope"] as const;

export function PurposeSection() {
  const t = useTranslations("mockup.info.purpose");
  return (
    <Section heading={t("heading")} testId="info-purpose">
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {PURPOSE_KEYS.map((key) => (
          <li key={key} className="border-2 border-border-soft rounded-xl bg-background p-4 text-base text-foreground-soft">
            {t(key)}
          </li>
        ))}
      </ul>
    </Section>
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
    <Section heading={t("heading")} testId="info-handling">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:items-center">
        <ul className="flex flex-col gap-4">
          {HANDLING.map(({ key, icon: Icon }) => (
            <li key={key} className="flex items-start gap-3 text-base text-foreground-soft">
              <span className="flex items-center justify-center w-9 h-9 shrink-0 rounded-full bg-kb/10 text-kb-dark">
                <Icon size={20} weight="bold" aria-hidden="true" />
              </span>
              <span className="pt-1.5">{t(key)}</span>
            </li>
          ))}
        </ul>
        <ScreenshotSlot caption={t("caption")} />
      </div>
    </Section>
  );
}

export function TeamSection() {
  const t = useTranslations("mockup.info.team");
  return (
    <Section heading={t("heading")} testId="info-team">
      <p className="text-base text-foreground-soft max-w-prose">{t("body")}</p>
      <div className="self-start rounded-md border-2 border-dashed border-border px-4 py-2 text-sm text-muted">
        {t("contact")}
      </div>
    </Section>
  );
}
