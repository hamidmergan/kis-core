"use client";

import { useTranslations } from "next-intl";
import { TOOL_ICONS } from "@/lib/toolIcons";
import type { ToolKey } from "@/lib/modules";
import Band from "./Band";
import { SectionHeading } from "./InfoSections";

const SERVICES: ToolKey[] = [
  "translation",
  "tts",
  "transcription",
  "interpreter",
  "summary",
  "podcast",
  "praesentation",
  "screencast",
  "image",
  "glossary",
];

/** The services teachers find on the start page, with the same texts as there. */
export default function ServiceGrid() {
  const t = useTranslations("mockup.info.services");
  const tools = useTranslations("startOverview.tools");
  return (
    <Band testId="info-services">
      <div className="flex flex-col gap-10">
        <div className="max-w-3xl flex flex-col gap-4">
          <SectionHeading>{t("heading")}</SectionHeading>
          <p className="text-lg @min-[40rem]:text-xl leading-relaxed text-foreground-soft">{t("intro")}</p>
        </div>
        <ul className="grid grid-cols-1 @min-[40rem]:grid-cols-2 @min-[64rem]:grid-cols-3 @min-[80rem]:grid-cols-5 gap-x-8 gap-y-10">
          {SERVICES.map((key) => {
            const Icon = TOOL_ICONS[key];
            return (
              <li key={key} className="flex flex-col gap-3" data-testid="service-item">
                <span className="flex items-center justify-center w-12 h-12 rounded-full bg-kb text-on-accent">
                  <Icon size={24} weight="bold" aria-hidden="true" />
                </span>
                <span className="text-lg font-semibold tracking-[-0.01em] text-foreground">{tools(`${key}.title`)}</span>
                <p className="text-base leading-relaxed text-foreground-soft">{tools(`${key}.body`)}</p>
              </li>
            );
          })}
        </ul>
      </div>
    </Band>
  );
}
