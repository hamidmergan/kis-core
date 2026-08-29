"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { useIsAdmin } from "@/hooks/useIsAdmin";

const BYPASS_PREFIXES = ["/maintenance", "/login", "/admin", "/api"];

export default function MaintenanceGuard() {
  const router = useRouter();
  const pathname = usePathname();
  const { isAdmin, loaded } = useIsAdmin();

  useEffect(() => {
    if (BYPASS_PREFIXES.some((p) => pathname?.startsWith(p))) return;
    if (!loaded) return;
    if (isAdmin) return;
    let cancelled = false;

    const check = async () => {
      try {
        const res = await fetch("/api/health/maintenance", { cache: "no-store" });
        if (!res.ok) return;
        const d = await res.json();
        if (!cancelled && d.enabled) router.replace("/maintenance");
      } catch {
        /* ignore */
      }
    };
    check();
    const id = setInterval(check, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, [pathname, router, isAdmin, loaded]);

  return null;
}
