"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Header from "@/components/layout/Header";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { checkAuthStatus } from "@/lib/auth";

export default function MaintenancePage() {
  const t = useTranslations("wartung");
  const { variant: mascotVariant } = useMascotPref();
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => setAuthenticated(!!s.authenticated));
  }, []);

  return (
    <>
      <Header showLogout={authenticated === true} />
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center space-y-4">
          <div className="flex justify-center">
            <Mascot variant={mascotVariant} size={140} state="idle" />
          </div>
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
