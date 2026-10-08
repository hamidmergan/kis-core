"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { CaretLeft } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";

/** The bar above a page, the module's top bar: way back on the left, the logo, tools on the right. */
export default function PageBar({ back, backLabel, children }: { back?: string; backLabel?: string; children?: React.ReactNode }) {
  const tHeader = useTranslations("header");
  return (
    <div className="kis-page-bar flex items-center px-5" style={{ height: 48 }}>
      {back && backLabel && (
        <>
          <Link
            href={back}
            title={backLabel}
            className="hidden sm:inline-flex items-center gap-1 mr-4 text-sm font-medium no-underline flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity min-w-0"
            style={{ color: "var(--muted)" }}
          >
            <CaretLeft size={13} weight="bold" />
            <span className="truncate" style={{ maxWidth: "14rem" }}>{backLabel}</span>
          </Link>
          {/* On a phone the way back is the round button of the module bar. */}
          <Link
            href={back}
            aria-label={backLabel}
            title={backLabel}
            className="sm:hidden w-7 h-7 mr-3 flex items-center justify-center rounded-full btn-icon flex-shrink-0 no-underline"
            style={{ backgroundColor: "var(--surface-dim)" }}
          >
            <CaretLeft size={15} weight="bold" />
          </Link>
        </>
      )}
      <Link href="/services" aria-label={tHeader("homeAria")} title={tHeader("homeAria")} className="flex items-center flex-shrink-0 no-underline logo-link">
        <Image src="/logos/kis-logo.svg" alt="KIS" width={228} height={78} className="h-6 w-auto" />
      </Link>
      {children && <div className="flex items-center gap-1.5 ml-auto">{children}</div>}
    </div>
  );
}
