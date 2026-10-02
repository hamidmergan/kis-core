"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { ArrowCircleRight, Bank, BookOpenText, Books, ChalkboardTeacher, Flask, GraduationCap, Quotes, WarningCircle, type Icon } from "@phosphor-icons/react";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import Band from "./Band";

/** Shared section heading, large on wide screens. */
export function SectionHeading({ children }: { children: ReactNode }) {
  return <h2 className="text-3xl @min-[40rem]:text-4xl font-semibold tracking-[-0.02em] leading-tight">{children}</h2>;
}

type PanelRow = { key: string; icon: Icon };

const PROJECT_ROWS: PanelRow[] = [
  { key: "funding", icon: Bank },
  { key: "pilot", icon: Flask },
  { key: "next", icon: ArrowCircleRight },
];

const PLATFORM_ROWS: PanelRow[] = [
  { key: "students", icon: GraduationCap },
  { key: "teachers", icon: ChalkboardTeacher },
  { key: "subjects", icon: Books },
];

/** One of the two panels that keep the project and the platform apart. */
function Panel({ group, rows, solid }: { group: "project" | "platform"; rows: PanelRow[]; solid: boolean }) {
  const t = useTranslations(`mockup.info.purpose.${group}`);
  return (
    <div className="flex flex-col gap-6 rounded-2xl border-2 border-border-soft bg-background p-6 @min-[40rem]:p-8" data-testid={`info-${group}`}>
      <div className="flex flex-col gap-3 items-start">
        <span
          className={`rounded-full px-3 py-1 text-sm font-semibold ${solid ? "bg-kb text-on-accent" : "bg-kb/10 text-kb-dark"}`}
        >
          {t("tag")}
        </span>
        <h3 className="text-2xl @min-[40rem]:text-3xl font-semibold tracking-[-0.02em] leading-tight">{t("title")}</h3>
        <p className="text-lg leading-relaxed text-foreground-soft">{t("body")}</p>
      </div>
      <ul className="flex flex-col gap-5 border-t-2 border-border-soft pt-6">
        {rows.map(({ key, icon: Icon }) => (
          <li key={key} className="flex items-start gap-4">
            <span className="flex items-center justify-center w-11 h-11 shrink-0 rounded-full bg-kb/10 text-kb-dark">
              <Icon size={24} weight="bold" aria-hidden="true" />
            </span>
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold uppercase tracking-wide text-muted">{t(`rows.${key}.label`)}</span>
              <span className="text-lg font-medium leading-snug">{t(`rows.${key}.value`)}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

const RULES: Array<{ key: "sources" | "names" | "errors"; icon: Icon }> = [
  { key: "sources", icon: BookOpenText },
  { key: "names", icon: Quotes },
  { key: "errors", icon: WarningCircle },
];

/** Project and platform as two separate panels, followed by how Francis treats questions. */
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
        <div className="grid grid-cols-1 @min-[48rem]:grid-cols-2 gap-4 @min-[40rem]:gap-6">
          <Panel group="project" rows={PROJECT_ROWS} solid={false} />
          <Panel group="platform" rows={PLATFORM_ROWS} solid />
        </div>
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
