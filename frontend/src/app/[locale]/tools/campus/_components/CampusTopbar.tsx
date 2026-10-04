"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { CaretLeft, NotePencil, SidebarSimple } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";

/** The bar above the chat: the way back to the services and the title, on the phone also history, bird and new chat. */
export default function CampusTopbar({
  title,
  onOpenMenu,
  onNew,
}: {
  title: string;
  onOpenMenu: () => void;
  onNew: () => void;
}) {
  const t = useTranslations("tools.campus");
  const tHeader = useTranslations("header");
  const tCommon = useTranslations("common");
  return (
    <div className="flex items-center gap-1 px-2 md:px-5 flex-shrink-0 relative" style={{ height: 48, borderBottom: "1px solid var(--border-soft)" }}>
      <button
        type="button"
        onClick={onOpenMenu}
        aria-label={t("openMenu")}
        title={t("openMenu")}
        className="md:hidden w-9 h-9 flex items-center justify-center rounded-full btn-icon"
        data-testid="campus-menu"
      >
        <SidebarSimple size={20} />
      </button>
      <Link
        href="/"
        aria-label={tHeader("homeAria")}
        title={tHeader("homeAria")}
        className="md:hidden flex items-center flex-shrink-0 no-underline logo-link"
      >
        <Image src="/logos/kis-vogel.svg" alt="KIS" width={154} height={78} className="h-5 w-auto" />
      </Link>
      <Link
        href="/services"
        title={tCommon("backToTools")}
        className="hidden md:inline-flex items-center gap-1 text-sm font-medium no-underline flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        style={{ color: "var(--muted)" }}
      >
        <CaretLeft size={13} weight="bold" />
        <span>{tCommon("backToTools")}</span>
      </Link>
      {/* Centred on wide screens, next to the bird on the phone where the middle is too narrow. */}
      <h1 className="md:hidden ml-2 text-base font-bold truncate min-w-0 flex-1" style={{ color: "var(--kb)" }}>{title}</h1>
      <span className="hidden md:flex absolute inset-0 items-center justify-center pointer-events-none">
        <h1 className="text-lg font-bold truncate pointer-events-auto select-text" style={{ color: "var(--kb)", maxWidth: "calc(100% - 16rem)" }}>
          {title}
        </h1>
      </span>
      <button
        type="button"
        onClick={onNew}
        aria-label={t("newChat")}
        title={t("newChat")}
        className="md:hidden w-9 h-9 flex items-center justify-center rounded-full btn-icon"
        data-testid="campus-new-chat-top"
      >
        <NotePencil size={20} />
      </button>
    </div>
  );
}
