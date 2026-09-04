"use client";

import { useTranslations } from "next-intl";
import { type CefrLevel } from "@/lib/cefr";

/** The level as a disc with its CEFR name, or just a hint while none is set. */
export function LevelMedallion({ level, sourceLine }: { level: CefrLevel | null; sourceLine: string | null }) {
  const t = useTranslations("languageLevel.languageTraining");

  if (!level) {
    return (
      <div className="flex flex-col items-center gap-6">
        <p className="max-w-md" style={{ color: "var(--muted)" }}>{t("noLevel")}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <p className="text-sm uppercase tracking-wider" style={{ color: "var(--muted)" }}>
        {t("levelLabel")}
      </p>
      <div
        className="flex items-center justify-center rounded-full font-bold"
        style={{
          width: 160,
          height: 160,
          fontSize: "3.5rem",
          lineHeight: 1,
          backgroundColor: "var(--kb)",
          color: "var(--on-accent)",
          boxShadow: "0 0 0 6px var(--background), 0 0 0 12px var(--surface-dim)",
        }}
      >
        {level}
      </div>
      <div className="flex flex-col items-center gap-1">
        <p className="font-semibold" style={{ color: "var(--foreground)" }}>
          {t(`levels.${level}.name`)}
        </p>
        <p className="text-sm max-w-md" style={{ color: "var(--muted)" }}>
          {t(`levels.${level}.short`)}
        </p>
      </div>
      {sourceLine && (
        <p className="text-xs" style={{ color: "var(--muted-soft)" }}>{sourceLine}</p>
      )}
    </div>
  );
}
