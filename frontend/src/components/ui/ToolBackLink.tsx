"use client";

import { CaretLeft } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

const CLASS = "flex w-fit items-center gap-1 text-sm font-medium -mt-4 mb-3 opacity-60 hover:opacity-100 transition-opacity";

/** With onRestart the link leads back to the empty first step, with href and label anywhere else, by default to the services. */
export default function ToolBackLink({ onRestart, href, label }: { onRestart?: () => void; href?: string; label?: string }) {
  const t = useTranslations("common");
  if (onRestart) {
    return (
      <button type="button" onClick={onRestart} className={CLASS} style={{ color: "var(--muted)" }}>
        <CaretLeft size={13} weight="bold" />
        {t("backToStart")}
      </button>
    );
  }
  return (
    <Link href={href ?? "/services"} className={CLASS} style={{ color: "var(--muted)" }}>
      <CaretLeft size={13} weight="bold" />
      {label ?? t("backToTools")}
    </Link>
  );
}
