"use client";

/** The menu of a custom role, on document.body instead of in the scrolling cell. */

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { DotsThreeVertical, PencilSimple, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";

const MENU_WIDTH = 200;
const GAP = 6;

export default function RoleMenu({
  onRename,
  onDelete,
}: {
  onRename: () => void;
  onDelete: () => void;
}) {
  const t = useTranslations("admin.roles");
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
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
      const left = Math.min(btn.right - MENU_WIDTH, window.innerWidth - MENU_WIDTH - 8);
      setPos({ top: btn.bottom + GAP, left: Math.max(8, left) });
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

  const row =
    "w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors";

  return (
    <>
      <IconButton
        ref={triggerRef}
        size="sm"
        onClick={(e: React.MouseEvent) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        title={t("more")}
        aria-label={t("more")}
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
          <button
            type="button"
            onClick={() => handle(onRename)}
            className={row}
            style={{ color: "var(--foreground)" }}
          >
            <PencilSimple size={16} weight="bold" />
            {t("edit")}
          </button>
          <button
            type="button"
            onClick={() => handle(onDelete)}
            className={row}
            style={{ color: "rgb(185, 28, 28)" }}
          >
            <Trash size={16} weight="bold" />
            {t("delete")}
          </button>
        </div>,
        document.body,
      )}
    </>
  );
}
