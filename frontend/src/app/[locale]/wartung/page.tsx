"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Wrench } from "@phosphor-icons/react";
import Hilde from "@/components/ui/Hilde";
import { useHildePref } from "@/hooks/useHildePref";

export default function MaintenancePage() {
  const t = useTranslations("wartung");
  const router = useRouter();
  const { enabled: hildeEnabled } = useHildePref();

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch("/api/health/maintenance", { cache: "no-store" });
        const d = await res.json();
        if (!d.enabled) router.replace("/");
      } catch {
        /* ignore */
      }
    };
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, [router]);

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
        <p className="text-xs text-muted-soft">{t("autoRefresh")}</p>
      </div>
    </div>
  );
}
