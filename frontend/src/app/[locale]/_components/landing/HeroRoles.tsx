"use client";

import { useTranslations } from "next-intl";
import Band from "./Band";
import Screenshot from "./Screenshot";
import { useBandTop } from "./useBandTop";

const H1 = "font-semibold tracking-[-0.02em] leading-[1.08] text-kb! dark:text-kb-dark!";

/** The two groups and what each does, every item is one message key. */
const ROLES = [
  { key: "teachers", items: ["services", "workspace"] },
  { key: "students", items: ["workspace", "practice", "answers"] },
] as const;

/** Says what the platform is, then what teachers and students do with it, the picture sits beside the text and on a phone between sentence and roles. */
export default function HeroRoles() {
  const t = useTranslations("eventInfo.hero");
  useBandTop("info-hero");
  return (
    <Band tone="hero" testId="info-hero" fill>
      <div className="grid grid-cols-1 gap-8 items-center @min-[48rem]:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] @min-[48rem]:[grid-template-areas:'head_shot'_'roles_shot'] @min-[48rem]:gap-x-12 @min-[48rem]:gap-y-10 @min-[64rem]:gap-x-20 @min-[80rem]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] @min-[80rem]:gap-x-12">
        <div className="flex flex-col gap-5 @min-[48rem]:[grid-area:head] @min-[48rem]:self-end">
          <h1 className={`${H1} text-4xl @min-[40rem]:text-5xl @min-[80rem]:text-6xl text-balance`}>
            {t.rich("title", {
              ask: (chunks) => <span className="font-extrabold text-kb dark:text-foreground">{chunks}</span>,
              francis: (chunks) => <span className="font-medium text-foreground">{chunks}</span>,
              br: () => <br />,
            })}
          </h1>
          <p className="text-lg @min-[40rem]:text-xl @min-[80rem]:text-2xl leading-relaxed text-foreground-soft max-w-2xl text-balance">{t("lead")}</p>
        </div>
        <div className="@min-[48rem]:[grid-area:shot]">
          <Screenshot name="workspace" alt={t("alt")} />
        </div>
        <div className="flex flex-col gap-6 max-w-2xl @min-[48rem]:[grid-area:roles] @min-[48rem]:self-start">
          {ROLES.map((role) => (
            <div key={role.key} className="border-l-[3px] border-kb dark:border-kb-dark pl-4">
              <h2 className="text-sm font-semibold uppercase tracking-[0.08em] text-kb dark:text-kb-dark mb-2">{t(`${role.key}.label`)}</h2>
              <ul className="list-disc pl-5 flex flex-col gap-1 text-base @min-[80rem]:text-lg leading-snug">
                {role.items.map((item) => (
                  <li key={item}>{t(`${role.key}.${item}`)}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </Band>
  );
}
