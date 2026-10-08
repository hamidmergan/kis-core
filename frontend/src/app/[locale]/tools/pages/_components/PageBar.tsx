"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

/** The bar above a page, the module's top bar: the logo on the left, tools on the right. */
export default function PageBar({ children }: { children?: React.ReactNode }) {
  const tHeader = useTranslations("header");
  return (
    <div className="kis-page-bar flex items-center px-5" style={{ height: 48 }}>
      <Link href="/services" aria-label={tHeader("homeAria")} title={tHeader("homeAria")} className="flex items-center flex-shrink-0 no-underline logo-link">
        <Image src="/logos/kis-logo.svg" alt="KIS" width={228} height={78} className="h-6 w-auto" />
      </Link>
      {children && <div className="flex items-center gap-1.5 ml-auto">{children}</div>}
    </div>
  );
}
