"use client";

import { useTranslations } from "next-intl";
import { FilePdf } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";

/** Der Weg zur Druckansicht, oben rechts auf der Seite. */
export default function ManualPrintLink() {
  const t = useTranslations("manual");

  return (
    <Link
      href="/manual/print"
      className="btn-outline-accent inline-flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium no-underline"
    >
      <FilePdf size={16} weight="bold" aria-hidden="true" />
      {t("printAll")}
    </Link>
  );
}
