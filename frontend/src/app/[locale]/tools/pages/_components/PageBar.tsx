"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

/** A button in the bar, the same as the header's Services and Calendar buttons. */
export const BAR_BUTTON = "flex items-center justify-center h-9 gap-1.5 rounded-full btn-on-dark flex-shrink-0";

/** The bar above a page, the blue header of the other pages: the logo on the left, tools on the right. */
export default function PageBar({ children }: { children?: React.ReactNode }) {
  const tHeader = useTranslations("header");
  return (
    <header className="kis-page-bar py-3 compact-on-short" style={{ backgroundColor: "var(--header-bg)", borderBottom: "1px solid var(--border)" }}>
      <div className="px-4 sm:px-6 flex items-center justify-between">
        <Link href="/services" aria-label={tHeader("homeAria")} title={tHeader("homeAria")} className="logo-link flex items-center flex-shrink-0">
          <Image src="/logos/kis-logo.svg" alt="KIS" width={228} height={78} className="h-8 w-auto" />
        </Link>
        {children && <div className="flex items-center gap-1.5">{children}</div>}
      </div>
    </header>
  );
}
