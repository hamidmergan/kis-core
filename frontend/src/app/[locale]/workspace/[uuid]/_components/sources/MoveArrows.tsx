import { useTranslations } from "next-intl";
import { CaretDown, CaretUp } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";

/** Up and down for one row while ordering, the ends grey out. */
export function MoveArrows({
  isFirst,
  isLast,
  onMove,
}: {
  isFirst: boolean;
  isLast: boolean;
  onMove: (direction: "up" | "down") => void;
}) {
  const t = useTranslations("workspace.detail.sources");
  return (
    <div className="flex-shrink-0 flex items-center gap-1 pl-1 pr-2">
      <IconButton
        data-testid="move-up"
        onClick={() => onMove("up")}
        disabled={isFirst}
        title={t("moveUp")}
        aria-label={t("moveUp")}
        className="disabled:opacity-40"
      >
        <CaretUp size={13} weight="bold" />
      </IconButton>
      <IconButton
        data-testid="move-down"
        onClick={() => onMove("down")}
        disabled={isLast}
        title={t("moveDown")}
        aria-label={t("moveDown")}
        className="disabled:opacity-40"
      >
        <CaretDown size={13} weight="bold" />
      </IconButton>
    </div>
  );
}
