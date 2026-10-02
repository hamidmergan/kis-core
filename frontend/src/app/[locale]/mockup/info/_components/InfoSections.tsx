"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Bank, BookOpenText, Flask, Quotes, RocketLaunch, Users, WarningCircle, type Icon } from "@phosphor-icons/react";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import Band from "./Band";

/** Shared section heading, large on wide screens. */
export function SectionHeading({ children }: { children: ReactNode }) {
  return <h2 className="text-3xl @min-[40rem]:text-4xl font-semibold tracking-[-0.02em] leading-tight">{children}</h2>;
}

const FACTS: Array<{ key: "who" | "pilot" | "funding" | "status"; icon: Icon }> = [
  { key: "who", icon: Users },
  { key: "pilot", icon: Flask },
  { key: "funding", icon: Bank },
  { key: "status", icon: RocketLaunch },
];

const RULES: Array<{ key: "sources" | "names" | "errors"; icon: Icon }> = [
  { key: "sources", icon: BookOpenText },
  { key: "names", icon: Quotes },
  { key: "errors", icon: WarningCircle },
];

/** Purpose of the project as a fact sheet, followed by how Francis treats questions. */
export function PurposeSection() {
  const t = useTranslations("mockup.info.purpose");
  const { variant } = useMascotPref();
  return (
    <Band testId="info-purpose">
      <div className="flex flex-col gap-10 @min-[40rem]:gap-14">
        <div className="grid grid-cols-1 @min-[64rem]:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] gap-6 @min-[64rem]:gap-16 items-start">
          <SectionHeading>{t("heading")}</SectionHeading>
          <p className="text-xl @min-[40rem]:text-2xl leading-snug text-foreground-soft text-balance">{t("lead")}</p>
        </div>
        <ul className="grid grid-cols-1 @min-[40rem]:grid-cols-2 @min-[80rem]:grid-cols-4 gap-4 @min-[40rem]:gap-6">
          {FACTS.map(({ key, icon: Icon }) => (
            <li key={key} className="flex flex-col gap-3 rounded-2xl border-2 border-border-soft bg-background p-6">
              <span className="flex items-center justify-center w-12 h-12 rounded-full bg-kb/10 text-kb-dark">
                <Icon size={26} weight="bold" aria-hidden="true" />
              </span>
              <span className="text-sm font-semibold uppercase tracking-wide text-muted">{t(`facts.${key}.label`)}</span>
              <span className="text-lg font-medium leading-snug">{t(`facts.${key}.value`)}</span>
            </li>
          ))}
        </ul>
        <div className="rounded-3xl border-2 border-border-soft bg-surface p-6 @min-[40rem]:p-10 flex flex-col gap-8">
          <div className="flex items-center gap-4">
            <span className="flex items-center justify-center w-14 h-14 shrink-0 rounded-full bg-kb text-on-accent">
              <Mascot variant={variant} size={52} state="idle" />
            </span>
            <h3 className="text-2xl @min-[40rem]:text-3xl font-semibold tracking-[-0.02em] leading-tight">{t("rulesHeading")}</h3>
          </div>
          <ul className="grid grid-cols-1 @min-[48rem]:grid-cols-3 gap-6 @min-[48rem]:gap-10">
            {RULES.map(({ key, icon: Icon }) => (
              <li key={key} className="flex items-start gap-4">
                <Icon size={28} weight="bold" className="shrink-0 mt-0.5 text-kb-dark" aria-hidden="true" />
                <p className="text-lg leading-relaxed text-foreground-soft">{t(`rules.${key}`)}</p>
              </li>
            ))}
          </ul>
        </div>
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
