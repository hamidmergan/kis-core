import { useTranslations } from "next-intl";
import { Check, Minus } from "@phosphor-icons/react";

/** Haken einer Gruppe: waehlt alle fertigen Dateien darin aus oder wieder ab.
 *
 *  Drei Zustaende, weil zwei nicht reichen: bei "einige" muss man sehen, dass
 *  die Gruppe angefasst wurde, ohne dass sie vollstaendig ist.
 *
 *  Nicht fertige Dateien bleiben aussen vor, genau wie bei "Alle auswaehlen".
 *  Der Chat bekaeme von ihnen nur leeren Zusammenhang.
 */
export function GroupCheckbox({
  state,
  disabled,
  onToggle,
}: {
  state: "none" | "some" | "all";
  disabled: boolean;
  onToggle: () => void;
}) {
  const t = useTranslations("workspace.detail.sources");
  const filled = state !== "none";
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); if (!disabled) onToggle(); }}
      disabled={disabled}
      aria-label={state === "all" ? t("deselectChapter") : t("selectChapter")}
      aria-checked={state === "all" ? "true" : state === "some" ? "mixed" : "false"}
      role="checkbox"
      className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
        filled
          ? "border-[var(--kb)] bg-[var(--kb)]"
          : disabled
          ? "border-[var(--border)] bg-background"
          : "border-[var(--border)] bg-background hover:border-[var(--kb)]"
      }`}
      style={{ color: "#fff", opacity: disabled ? 0.5 : 1 }}
    >
      {state === "all" && <Check size={11} weight="bold" />}
      {state === "some" && <Minus size={11} weight="bold" />}
    </button>
  );
}
