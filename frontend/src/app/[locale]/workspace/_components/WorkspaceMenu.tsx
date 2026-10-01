"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { DotsThreeVertical, Info, LinkSimple, PencilSimple, SignOut, Star, Trash, Users } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";

interface WorkspaceMenuProps {
  /** Every entry appears only when it exists for this row. */
  favorite?: boolean;
  onToggleFavorite?: () => void;
  /** Full description, phone only — the desktop row unfolds it inline instead. */
  onInfo?: () => void;
  onParticipants?: () => void;
  onLinks?: () => void;
  onEdit?: () => void;
  /** Left out for tutors: deleting the workspace stays with the owner. */
  onDelete?: () => void;
  /** Demo courses only, real courses cannot be left here. */
  onLeave?: () => void;
  testId?: string;
}

const MENU_WIDTH = 220;
const GAP = 6;

export default function WorkspaceMenu({
  favorite, onToggleFavorite, onInfo, onParticipants, onLinks, onEdit, onDelete, onLeave, testId,
}: WorkspaceMenuProps) {
  const t = useTranslations("workspace.list");
  const tDemo = useTranslations("workspace.demo");
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      const t = e.target as Node;
      if (triggerRef.current?.contains(t)) return;
      if (menuRef.current?.contains(t)) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    function update() {
      const btn = triggerRef.current?.getBoundingClientRect();
      if (!btn) return;
      const top = btn.bottom + GAP;
      const left = Math.min(btn.right - MENU_WIDTH, window.innerWidth - MENU_WIDTH - 8);
      setPos({ top, left: Math.max(8, left) });
    }
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [open]);

  function handle(action: () => void) {
    setOpen(false);
    action();
  }

  return (
    <>
      <IconButton
        ref={triggerRef}
        onClick={(e: React.MouseEvent) => { e.stopPropagation(); setOpen(!open); }}
        title={t("more")}
        data-testid={testId}
      >
        <DotsThreeVertical size={13} weight="bold" />
      </IconButton>
      {open && pos && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          className="fixed z-50 rounded-xl py-1"
          style={{
            top: pos.top,
            left: pos.left,
            width: MENU_WIDTH,
            backgroundColor: "var(--surface)",
            border: "1px solid var(--border)",
            boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
          }}
        >
          {onToggleFavorite && (
          <button
            type="button"
            onClick={() => handle(onToggleFavorite)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
            style={{ color: "var(--foreground)" }}
          >
            <Star size={16} weight={favorite ? "fill" : "bold"} className={favorite ? "text-kb-dark" : undefined} />
            {favorite ? t("favoriteRemove") : t("favoriteAdd")}
          </button>
          )}
          {onInfo && (
          <button
            type="button"
            onClick={() => handle(onInfo)}
            className="sm:hidden w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
            style={{ color: "var(--foreground)" }}
          >
            <Info size={16} weight="bold" />
            {t("descriptionField")}
          </button>
          )}
          {onParticipants && (
          <button
            type="button"
            onClick={() => handle(onParticipants)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
            style={{ color: "var(--foreground)" }}
          >
            <Users size={16} weight="bold" />
            {t("participants")}
          </button>
          )}
          {onLinks && (
          <button
            type="button"
            onClick={() => handle(onLinks)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
            style={{ color: "var(--foreground)" }}
          >
            <LinkSimple size={16} weight="bold" />
            {t("linksTitle")}
          </button>
          )}
          {onEdit && (
          <button
            type="button"
            onClick={() => handle(onEdit)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
            style={{ color: "var(--foreground)" }}
          >
            <PencilSimple size={16} weight="bold" />
            {t("edit")}
          </button>
          )}
          {onLeave && (
            <button
              type="button"
              data-testid="demo-leave-row"
              onClick={() => handle(onLeave)}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
              style={{ color: "var(--foreground)" }}
            >
              <SignOut size={16} weight="bold" />
              {tDemo("leave")}
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              onClick={() => handle(onDelete)}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
              style={{ color: "rgb(185, 28, 28)" }}
            >
              <Trash size={16} weight="bold" />
              {t("delete")}
            </button>
          )}
        </div>,
        document.body,
      )}
    </>
  );
}
