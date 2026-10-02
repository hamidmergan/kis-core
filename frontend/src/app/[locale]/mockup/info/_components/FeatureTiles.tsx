"use client";

import { useTranslations } from "next-intl";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { MOCKUP_ICONS } from "../../_lib/icons";
import type { IconKey } from "../../_lib/types";
import Band from "./Band";
import { SectionHeading } from "./InfoSections";
import ScreenshotSlot from "./ScreenshotSlot";

const FEATURES: IconKey[] = ["francis", "translation", "tts", "transcription", "interpreter", "summary"];

/** The services as cards with a screenshot on top, nothing to click because the page is public. */
export default function FeatureTiles() {
  const t = useTranslations("mockup.info.features");
  const { variant } = useMascotPref();
  return (
    <Band tone="tint" testId="info-features">
      <div className="flex flex-col gap-10">
        <SectionHeading>{t("heading")}</SectionHeading>
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {FEATURES.map((key) => {
            const Icon = MOCKUP_ICONS[key];
            return (
              <li key={key} className="flex flex-col gap-5 text-foreground" data-testid="feature-tile">
                <ScreenshotSlot
                  compact
                  icon={
                    key === "francis" ? (
                      <Mascot variant={variant} size={64} state="idle" />
                    ) : (
                      <Icon size={40} weight="light" aria-hidden="true" />
                    )
                  }
                />
                <div>
                  <span className="block text-xl font-semibold tracking-[-0.01em]">{t(`items.${key}.title`)}</span>
                  <p className="text-base leading-relaxed text-foreground-soft mt-1.5">{t(`items.${key}.body`)}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </Band>
  );
}
