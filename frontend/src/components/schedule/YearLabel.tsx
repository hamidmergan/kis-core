import { Question } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import HoverTooltip from "@/components/ui/HoverTooltip";

/** The year of an appointment, marked when the source wrote none and the system picked it. */
export function YearLabel({
  year,
  label,
  assumed,
}: {
  year: string;
  /** Shorter form for narrow badges, the tooltip always names the full year. */
  label?: string;
  assumed?: boolean | null;
}) {
  const t = useTranslations("schedule");
  if (!assumed) return <>{label ?? year}</>;
  return (
    <HoverTooltip text={t("yearAssumed", { jahr: year })} tapToOpen>
      <span
        tabIndex={0}
        aria-label={`${label ?? year}, ${t("yearAssumedAria")}`}
        className="inline-flex items-center gap-0.5 cursor-help"
      >
        {label ?? year}
        <Question size={9} weight="bold" style={{ color: "var(--kb)" }} />
      </span>
    </HoverTooltip>
  );
}
