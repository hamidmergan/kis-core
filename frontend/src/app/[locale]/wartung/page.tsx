"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Wrench } from "@phosphor-icons/react";
import Hilde from "@/components/ui/Hilde";
import { useHildePref } from "@/hooks/useHildePref";

export default function MaintenancePage() {
  const t = useTranslations("wartung");
  const { enabled: hildeEnabled } = useHildePref();

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-4">
        {hildeEnabled ? (
          <div className="flex justify-center">
            <Hilde size={140} state="idle" />
          </div>
        ) : (
          <Wrench size={56} weight="bold" className="mx-auto text-muted" />
        )}
        <h1 className="text-2xl font-semibold text-foreground">{t("title")}</h1>
        <p className="text-sm text-foreground-soft">
          {t("body")}
        </p>
        <div className="pt-2">
          <Link href="/login" className="text-sm text-kb hover:underline">
            {t("backToLogin")}
          </Link>
        </div>
      </div>
    </div>
  );
}
