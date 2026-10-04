"use client";

import { useTranslations } from "next-intl";
import { SidebarSimple } from "@phosphor-icons/react";

/** The phone bar above the chat: only the history button, logo and new chat sit in the history. */
export default function CampusTopbar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const t = useTranslations("tools.campus");
  return (
    <div className="md:hidden flex items-center gap-1 px-2 flex-shrink-0" style={{ height: 48, borderBottom: "1px solid var(--border-soft)" }}>
      <button
        type="button"
        onClick={onOpenMenu}
        aria-label={t("openMenu")}
        title={t("openMenu")}
        className="w-9 h-9 flex items-center justify-center rounded-full btn-icon"
        data-testid="campus-menu"
      >
        <SidebarSimple size={20} />
      </button>
    </div>
  );
}
