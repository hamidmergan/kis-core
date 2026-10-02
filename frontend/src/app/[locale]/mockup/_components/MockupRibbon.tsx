"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { ROUTES } from "../_lib/routes";

export default function MockupRibbon() {
  const t = useTranslations("mockup.common");
  return (
    <div className="border-b border-border-soft bg-surface px-4 py-2 text-xs text-foreground-soft flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="font-semibold text-kb-dark">{t("ribbon")}</span>
      <span>{t("ribbonHint")}</span>
      <Link href={ROUTES.overview} className="underline hover:text-kb">
        {t("backToOverview")}
      </Link>
    </div>
  );
}
