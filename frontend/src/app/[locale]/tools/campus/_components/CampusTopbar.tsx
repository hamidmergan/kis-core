"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { NotePencil, SidebarSimple } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";

/** The phone bar above the chat: history, bird home and new chat. The desktop has all of it in the sidebar. */
export default function CampusTopbar({ onOpenMenu, onNew }: { onOpenMenu: () => void; onNew: () => void }) {
  const t = useTranslations("tools.campus");
  const tHeader = useTranslations("header");
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
      <Link href="/" aria-label={tHeader("homeAria")} title={tHeader("homeAria")} className="flex items-center flex-shrink-0 no-underline logo-link ml-1">
        <Image src="/logos/kis-vogel.svg" alt="KIS" width={154} height={78} className="h-5 w-auto" />
      </Link>
      <button
        type="button"
        onClick={onNew}
        aria-label={t("newChat")}
        title={t("newChat")}
        className="ml-auto w-9 h-9 flex items-center justify-center rounded-full btn-icon"
        data-testid="campus-new-chat-top"
      >
        <NotePencil size={20} />
      </button>
    </div>
  );
}
