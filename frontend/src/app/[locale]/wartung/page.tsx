"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Wrench } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import Hilde from "@/components/ui/Hilde";
import { useHildePref } from "@/hooks/useHildePref";
import { checkAuthStatus } from "@/lib/auth";

export default function MaintenancePage() {
  const t = useTranslations("wartung");
  const { enabled: hildeEnabled } = useHildePref();
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => setAuthenticated(!!s.authenticated));
  }, []);

  return (
    <>
      <Header showLogout={authenticated === true} />
      <div className="min-h-[70vh] flex items-center justify-center px-4">
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
          {authenticated === false && (
            <div className="pt-2">
              <Link href="/login" className="text-sm text-kb hover:underline">
                {t("backToLogin")}
              </Link>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
