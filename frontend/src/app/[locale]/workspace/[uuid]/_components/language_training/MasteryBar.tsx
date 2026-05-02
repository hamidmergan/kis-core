import { useTranslations } from "next-intl";
import type { StudentStats } from "../../_types";

export function MasteryBar({ stats }: { stats: StudentStats | null }) {
  const t = useTranslations("workspace.detail.languageTraining.mastery");
  if (!stats) return null;
  const o = stats.lerntools;
  return (
    <div className="px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold" style={{ color: "var(--foreground)" }}>
          {t("exercisesCount", { count: o.total_sets })} · {t("cardsLabel", { count: o.total_cards })}
        </span>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{t("answersLabel", { count: o.total_attempts })}</span>
      </div>
    </div>
  );
}
