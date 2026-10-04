"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { CaretLeft, List, X } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";

/** The slim bar of the page: logo home, the way back to the services and the title. */
export default function CampusTopbar({
  title,
  menuOpen,
  onToggleMenu,
}: {
  title: string;
  menuOpen: boolean;
  onToggleMenu: () => void;
}) {
  const tHeader = useTranslations("header");
  const tCommon = useTranslations("common");
  return (
    <div className="flex items-center px-3 sm:px-5 flex-shrink-0 relative" style={{ height: 48, borderBottom: "1px solid var(--border-soft)" }}>
      <button
        type="button"
        onClick={onToggleMenu}
        aria-expanded={menuOpen}
        aria-label={menuOpen ? tHeader("menuClose") : tHeader("menuOpen")}
        className="md:hidden w-8 h-8 flex items-center justify-center rounded-full btn-icon mr-2"
        data-testid="campus-menu"
      >
        {menuOpen ? <X size={18} weight="bold" /> : <List size={18} weight="bold" />}
      </button>
      <Link
        href="/services"
        title={tCommon("backToTools")}
        className="hidden md:inline-flex items-center gap-1 mr-4 text-sm font-medium no-underline flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        style={{ color: "var(--muted)" }}
      >
        <CaretLeft size={13} weight="bold" />
        <span>{tCommon("backToTools")}</span>
      </Link>
      <Link
        href="/services"
        aria-label={tHeader("homeAria")}
        title={tHeader("homeAria")}
        className="flex items-center gap-1.5 flex-shrink-0 no-underline logo-link"
      >
        <Image src="/logos/kis-logo.svg" alt="KIS" width={228} height={78} className="h-6 w-auto" />
      </Link>
      {/* Centred on wide screens, next to the logo on the phone where the middle is too narrow. */}
      <h1 className="md:hidden ml-3 text-base font-bold truncate min-w-0" style={{ color: "var(--kb)" }}>{title}</h1>
      <span className="hidden md:flex absolute inset-0 items-center justify-center pointer-events-none">
        <h1 className="text-lg font-bold truncate pointer-events-auto select-text" style={{ color: "var(--kb)", maxWidth: "calc(100% - 16rem)" }}>
          {title}
        </h1>
      </span>
    </div>
  );
}
