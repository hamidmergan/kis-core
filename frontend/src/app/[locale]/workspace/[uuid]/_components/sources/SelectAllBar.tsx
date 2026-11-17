import { useTranslations } from "next-intl";
import { Check, FolderSimple, PencilSimple, X } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import type { Chapter, Source } from "../../_types";
import { OwnerOnly } from "../layout/OwnerOnly";
import { MenuItem } from "./SourceRow";

/** Select all row. The pencil switches to move mode, then the row shows in brand blue that selection is for moving. */
export function SelectAllBar({
  moving,
  canMove,
  canArrange,
  compact,
  allSelected,
  onToggleAll,
  onStartMoving,
  onStopMoving,
  chapters,
  checkedSources,
  chapterOf,
  menuOpen,
  onMenuOpen,
  onMoveChecked,
}: {
  moving: boolean;
  /** Moving into chapters only exists with chapters. */
  canMove: boolean;
  canArrange: boolean;
  compact: boolean;
  allSelected: boolean;
  onToggleAll: () => void;
  onStartMoving: () => void;
  onStopMoving: () => void;
  chapters: Chapter[];
  /** The files picked for moving. */
  checkedSources: Source[];
  chapterOf: (source: Source) => string | null;
  menuOpen: boolean;
  onMenuOpen: (open: boolean) => void;
  onMoveChecked: (chapterUuid: string | null) => void;
}) {
  const t = useTranslations("workspace.detail.sources");
  return (
    <div
      onClick={moving && !canMove ? undefined : onToggleAll}
      data-testid={moving ? "move-bar" : undefined}
      className="sources-select-all flex items-center gap-3 px-4 py-2 flex-shrink-0 cursor-pointer"
      style={moving
        ? { backgroundColor: "rgba(var(--kb-rgb),0.12)", borderBottom: "2px solid var(--kb)" }
        : { borderBottom: "1px solid var(--border)" }}
    >
      <button
        type="button"
        aria-label={allSelected ? t("deselectAll") : t("selectAll")}
        className={`${moving && !canMove ? "invisible" : ""} flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
          allSelected
            ? "border-[var(--kb)] bg-[var(--kb)]"
            : "border-[var(--border)] bg-background hover:border-[var(--kb)]"
        }`}
        style={{ color: "#fff" }}
      >
        {allSelected && <Check size={11} weight="bold" />}
      </button>
      <span
        className={`flex-1 min-w-0 truncate text-sm ${moving ? "font-medium" : ""}`}
        style={moving ? { color: "var(--kb)" } : undefined}
      >
        {moving ? (canMove ? t("moveModeHint") : t("arrangeModeHint")) : t("selectAll")}
      </span>
      <OwnerOnly show={canArrange}>
        <div className="relative flex-shrink-0 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          {moving ? (
            <>
              {canMove && <button
                type="button"
                data-testid="move-checked"
                disabled={checkedSources.length === 0}
                onClick={() => onMenuOpen(!menuOpen)}
                className="btn-primary flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium disabled:opacity-50"
              >
                <FolderSimple size={13} weight="bold" />
                {compact ? checkedSources.length : t("moveChecked", { count: checkedSources.length })}
              </button>}
              <IconButton
                data-testid="move-cancel"
                onClick={onStopMoving}
                title={t("cancel")}
                aria-label={t("cancel")}
              >
                <X size={13} weight="bold" />
              </IconButton>
            </>
          ) : (
            <IconButton
              data-testid="move-mode"
              onClick={onStartMoving}
              title={canMove ? t("moveModeStart") : t("arrangeModeStart")}
              aria-label={canMove ? t("moveModeStart") : t("arrangeModeStart")}
              className="text-[var(--kb)]"
              style={{ backgroundColor: "rgba(var(--kb-rgb),0.10)" }}
            >
              <PencilSimple size={13} weight="bold" />
            </IconButton>
          )}
          {moving && menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => onMenuOpen(false)} />
              <div
                className="absolute right-0 top-8 z-50 rounded-xl py-1"
                style={{
                  backgroundColor: "var(--surface)",
                  border: "1px solid var(--border)",
                  minWidth: 200,
                  maxHeight: "16rem",
                  overflowY: "auto",
                  boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                }}
              >
                {chapters.map((c) => (
                  <MenuItem
                    key={c.uuid}
                    icon={<FolderSimple size={16} weight="bold" />}
                    label={c.name}
                    disabled={checkedSources.every((s) => chapterOf(s) === c.uuid)}
                    onClick={() => onMoveChecked(c.uuid)}
                  />
                ))}
                <MenuItem
                  icon={<FolderSimple size={16} weight="bold" />}
                  label={t("noChapter")}
                  disabled={checkedSources.every((s) => chapterOf(s) === null)}
                  onClick={() => onMoveChecked(null)}
                />
              </div>
            </>
          )}
        </div>
      </OwnerOnly>
    </div>
  );
}
