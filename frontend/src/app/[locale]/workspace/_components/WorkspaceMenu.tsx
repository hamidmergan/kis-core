"use client";

import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { DotsThreeVertical, Info, LinkSimple, PencilSimple, SignOut, Star, Trash, Users } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { useAnchoredMenu } from "@/hooks/useAnchoredMenu";

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

/** One entry of the menu, `className` only prefixes the shared classes. */
function MenuItem({ onClick, icon, label, className = "", color = "var(--foreground)", testId }: {
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  className?: string;
  color?: string;
  testId?: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`${className}w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors`}
      style={{ color }}
    >
      {icon}
      {label}
    </button>
  );
}

export default function WorkspaceMenu({
  favorite, onToggleFavorite, onInfo, onParticipants, onLinks, onEdit, onDelete, onLeave, testId,
}: WorkspaceMenuProps) {
  const t = useTranslations("workspace.list");
  const tDemo = useTranslations("workspace.demo");
  const { open, setOpen, pos, triggerRef, menuRef } = useAnchoredMenu(MENU_WIDTH, GAP);

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
            <MenuItem
              onClick={() => handle(onToggleFavorite)}
              icon={<Star size={16} weight={favorite ? "fill" : "bold"} className={favorite ? "text-kb-dark" : undefined} />}
              label={favorite ? t("favoriteRemove") : t("favoriteAdd")}
            />
          )}
          {onInfo && (
            <MenuItem onClick={() => handle(onInfo)} icon={<Info size={16} weight="bold" />} label={t("descriptionField")} className="sm:hidden " />
          )}
          {onParticipants && (
            <MenuItem onClick={() => handle(onParticipants)} icon={<Users size={16} weight="bold" />} label={t("participants")} />
          )}
          {onLinks && (
            <MenuItem onClick={() => handle(onLinks)} icon={<LinkSimple size={16} weight="bold" />} label={t("linksTitle")} />
          )}
          {onEdit && (
            <MenuItem onClick={() => handle(onEdit)} icon={<PencilSimple size={16} weight="bold" />} label={t("edit")} />
          )}
          {onLeave && (
            <MenuItem onClick={() => handle(onLeave)} icon={<SignOut size={16} weight="bold" />} label={tDemo("leave")} testId="demo-leave-row" />
          )}
          {onDelete && (
            <MenuItem onClick={() => handle(onDelete)} icon={<Trash size={16} weight="bold" />} label={t("delete")} color="rgb(185, 28, 28)" />
          )}
        </div>,
        document.body,
      )}
    </>
  );
}
