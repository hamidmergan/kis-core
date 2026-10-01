"use client";

import { CaretLeft } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

export default function ToolBackLink() {
  const t = useTranslations("common");
  return (
    <Link
      href="/"
      className="inline-flex items-center gap-1 text-sm font-medium mb-3 opacity-60 hover:opacity-100 transition-opacity"
      style={{ color: "var(--muted)" }}
    >
      <CaretLeft size={13} weight="bold" />
      {t("backToTools")}
    </Link>
  );
}
