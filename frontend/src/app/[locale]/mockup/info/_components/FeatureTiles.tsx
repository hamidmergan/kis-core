"use client";

import { useTranslations } from "next-intl";
import { MOCKUP_ICONS } from "../../_lib/icons";
import type { IconKey } from "../../_lib/types";
import { Section } from "./InfoSections";

const FEATURES: IconKey[] = ["francis", "translation", "tts", "transcription", "interpreter", "summary"];

/** The services as calm tiles, nothing to click because the page is public. */
export default function FeatureTiles() {
  const t = useTranslations("mockup.info.features");
  return (
    <Section heading={t("heading")} testId="info-features">
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {FEATURES.map((key) => {
          const Icon = MOCKUP_ICONS[key];
          return (
            <li
              key={key}
              className="flex items-start gap-4 border-2 border-[var(--tile-border)] rounded-2xl bg-[var(--tile-bg)] p-5 text-foreground"
              style={{ boxShadow: "var(--shadow)" }}
              data-testid="feature-tile"
            >
              <span className="flex items-center justify-center w-12 h-12 shrink-0 rounded-full bg-kb text-on-accent">
                <Icon size={24} weight="bold" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <span className="block text-base font-semibold tracking-[-0.01em]">{t(`items.${key}.title`)}</span>
                <p className="text-sm leading-[21px] text-foreground-soft mt-1">{t(`items.${key}.body`)}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </Section>
  );
}
