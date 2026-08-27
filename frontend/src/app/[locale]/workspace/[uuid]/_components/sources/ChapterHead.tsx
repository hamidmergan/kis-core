import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  CaretDown,
  CaretUp,
  DotsThreeVertical,
  PencilSimple,
  Trash,
} from "@phosphor-icons/react";
import type { Chapter } from "../../_types";
import { MenuItem } from "./SourceRow";
import { GroupCheckbox } from "./GroupCheckbox";

/** Header of a chapter, the checkbox only sets the checkboxes of the files in it. */
export function ChapterHead({
  chapter,
  count,
  selectState,
  selectDisabled,
  onToggleSelect,
  open,
  isOwner,
  compact,
  isFirst,
  isLast,
  menuOpen,
  onMenuOpen,
  renaming,
  onRenameStart,
  onRenameEnd,
  onToggleOpen,
  onRename,
  onMove,
  onDelete,
}: {
  chapter: Chapter;
  count: number;
  /** Derived from the file checkboxes in the chapter, not stored itself. */
  selectState: "none" | "some" | "all";
  selectDisabled: boolean;
  onToggleSelect: () => void;
  open: boolean;
  isOwner: boolean;
  compact: boolean;
  isFirst: boolean;
  isLast: boolean;
  menuOpen: boolean;
  onMenuOpen: (open: boolean) => void;
  renaming: boolean;
  onRenameStart: () => void;
  onRenameEnd: () => void;
  onToggleOpen: () => void;
  onRename: (uuid: string, name: string) => Promise<void>;
  onMove: (uuid: string, direction: "up" | "down") => void;
  onDelete: (chapter: Chapter) => void;
}) {
  const t = useTranslations("workspace.detail.sources");
  const [value, setValue] = useState(chapter.name);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renaming) {
      setValue(chapter.name);
      setError(null);
      inputRef.current?.select();
    }
  }, [renaming, chapter.name]);

  async function commit() {
    if (busy) return;
    const next = value.trim();
    if (!next || next === chapter.name) {
      onRenameEnd();
      setError(null);
      return;
    }
    setBusy(true);
    try {
      await onRename(chapter.uuid, next);
      onRenameEnd();
      setError(null);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : t("chapterRenameFailed"));
    } finally {
      setBusy(false);
    }
  }

  if (renaming) {
    return (
      <div
        className="relative flex items-center gap-2 px-3 py-2"
        style={{ backgroundColor: "var(--surface-dim)", borderBottom: "1px solid var(--border)" }}
      >
        <input
          ref={inputRef}
          value={value}
          disabled={busy}
          autoFocus
          placeholder={t("chapterNamePlaceholder")}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); commit(); }
            if (e.key === "Escape") { e.preventDefault(); onRenameEnd(); setError(null); }
          }}
          onBlur={() => commit()}
          className="flex-1 min-w-0 text-sm px-2 py-1 rounded-md border-2 bg-background"
          style={{ borderColor: "var(--kb)", color: "var(--foreground)" }}
        />
        {error && (
          <div
            className="absolute left-3 right-3 top-full z-10 mt-1 rounded-lg px-3 py-2 text-xs leading-snug shadow-lg"
            style={{ backgroundColor: "#FEF2F2", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}
          >
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className="relative flex items-center gap-2 pl-4 pr-2 py-2 select-none"
      style={{ backgroundColor: "var(--surface-dim)", borderBottom: "1px solid var(--border)" }}
    >
      <GroupCheckbox state={selectState} disabled={selectDisabled} onToggle={onToggleSelect} />
      <button
        type="button"
        onClick={onToggleOpen}
        aria-expanded={open}
        aria-label={open ? t("collapseChapter") : t("expandChapter")}
        className="flex-1 flex items-center gap-2 min-w-0 text-left"
      >
        <CaretDown
          size={13}
          weight="bold"
          style={{
            flexShrink: 0,
            color: "var(--foreground-soft)",
            transform: open ? "rotate(0deg)" : "rotate(-90deg)",
            transition: "transform 150ms",
          }}
        />
        <span
          className="flex-1 text-sm font-semibold truncate min-w-0"
          style={{ color: "var(--foreground)" }}
          title={chapter.name}
        >
          {chapter.name}
        </span>
        <span className="text-xs flex-shrink-0" style={{ color: "var(--foreground-soft)" }}>
          {count}
        </span>
      </button>

      {isOwner && !compact && (
        <div className="relative flex-shrink-0">
          <button
            type="button"
            onClick={() => onMenuOpen(!menuOpen)}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            title={t("options")}
          >
            <DotsThreeVertical size={16} weight="bold" />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => onMenuOpen(false)} />
              <div
                className="absolute right-0 top-9 z-50 rounded-xl py-1"
                style={{
                  backgroundColor: "var(--surface)",
                  border: "1px solid var(--border)",
                  minWidth: 200,
                  boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                }}
              >
                <MenuItem
                  icon={<PencilSimple size={16} weight="bold" />}
                  label={t("rename")}
                  onClick={() => { onMenuOpen(false); onRenameStart(); }}
                />
                <MenuItem
                  icon={<CaretUp size={16} weight="bold" />}
                  label={t("moveUp")}
                  disabled={isFirst}
                  onClick={() => { onMenuOpen(false); onMove(chapter.uuid, "up"); }}
                />
                <MenuItem
                  icon={<CaretDown size={16} weight="bold" />}
                  label={t("moveDown")}
                  disabled={isLast}
                  onClick={() => { onMenuOpen(false); onMove(chapter.uuid, "down"); }}
                />
                <div className="my-1" style={{ height: 1, backgroundColor: "var(--border)" }} />
                <MenuItem
                  icon={<Trash size={16} weight="bold" />}
                  label={t("deleteChapter")}
                  danger
                  onClick={() => { onMenuOpen(false); onDelete(chapter); }}
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
