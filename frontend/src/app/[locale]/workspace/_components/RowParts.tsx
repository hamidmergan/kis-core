"use client";

import { useTranslations } from "next-intl";
import { Star } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";

/** Marks a row of the demo account. */
export function DemoBadge() {
  const tDemo = useTranslations("workspace.demo");
  return (
    <span
      className="flex-shrink-0 text-3xs font-semibold px-1.5 py-0.5 rounded"
      style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
    >
      {tDemo("button")}
    </span>
  );
}

/** The star of a row, the click never opens the workspace behind it. */
export function FavoriteButton({ favorite, disabled, onToggle }: { favorite: boolean; disabled: boolean; onToggle: () => void }) {
  const t = useTranslations("workspace.list");
  return (
    <IconButton
      onClick={(e: React.MouseEvent) => { e.stopPropagation(); onToggle(); }}
      title={favorite ? t("favoriteRemove") : t("favoriteAdd")}
      className={favorite ? "text-kb-dark" : ""}
      disabled={disabled}
      data-testid="workspace-favorite"
    >
      <Star size={13} weight={favorite ? "fill" : "bold"} />
    </IconButton>
  );
}
