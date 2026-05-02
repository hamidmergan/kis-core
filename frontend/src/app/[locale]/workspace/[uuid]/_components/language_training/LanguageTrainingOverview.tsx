import { BookOpenText, Exam, TextAa } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { LanguageTrainingView } from "../../_types";

export function LanguageTrainingOverview({
  activeSourceCount, glossaryCount, onNavigate,
}: {
  activeSourceCount: number;
  glossaryCount: number;
  onNavigate: (view: LanguageTrainingView) => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const noSources = activeSourceCount === 0;

  const tiles = [
    { key: "lk-sets" as const, Icon: BookOpenText, label: t("overview.lernkarten"), desc: t("overview.tileDesc"), iconBg: "var(--badge-amber-bg)", iconColor: "var(--badge-amber-fg)" },
    { key: "cl-sets" as const, Icon: TextAa, label: t("overview.lueckentext"), desc: t("overview.tileDesc"), iconBg: "var(--badge-red-bg)", iconColor: "var(--badge-red-fg)" },
    { key: "vt-sets" as const, Icon: Exam, label: t("overview.begriffeQuiz"), desc: t("overview.tileDesc"), iconBg: "var(--badge-violet-bg)", iconColor: "var(--badge-violet-fg)" },
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {/* Glossary counter */}
        {glossaryCount > 0 && (
          <span className="text-xs font-medium px-1" style={{ color: "var(--muted)" }}>
            {t("overview.glossaryCounter", { count: glossaryCount, max: 150 })}
          </span>
        )}

        {/* Tool tiles */}
        <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}>
          {tiles.map((tile) => {
            const disabled = noSources;
            return (
              <button
                key={tile.key}
                type="button"
                onClick={() => !disabled && onNavigate(tile.key)}
                disabled={disabled}
                className="flex flex-col items-center justify-center gap-1.5 p-3 rounded-2xl text-center border-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed border-[var(--tile-border)] enabled:hover:border-[var(--tile-color)]"
                style={{
                  minHeight: 85,
                  backgroundColor: tile.iconBg,
                  ["--tile-color" as string]: tile.iconColor,
                  ["--tile-border" as string]: `${tile.iconColor}22`,
                }}
              >
                <tile.Icon size={20} color={tile.iconColor} weight="bold" />
                <span className="text-xs font-semibold leading-tight" style={{ color: tile.iconColor }}>
                  {tile.label}
                </span>
                <span className="text-xs" style={{ color: tile.iconColor, opacity: 0.7 }}>
                  {tile.desc}
                </span>
              </button>
            );
          })}
        </div>

      </div>
    </div>
  );
}
