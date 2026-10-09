"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import { PUBLIC_PAGES } from "@/lib/api";

const BYPASS_PREFIXES = ["/consent", "/login", "/maintenance", "/api"];

/** Blocks every service until the account has confirmed the notice, same for TH, external or demo access. */
export default function ConsentGuard() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Public pages (landing, map, imprint, privacy) stay reachable without consenting -
    // the privacy link inside the consent text would otherwise bounce right back here.
    if (pathname && PUBLIC_PAGES.includes(pathname)) return;
    if (BYPASS_PREFIXES.some((p) => pathname?.startsWith(p))) return;
    let cancelled = false;

    checkAuthStatus().then((status) => {
      if (cancelled) return;
      if (!status.authenticated) return;
      // A borrowed account shows the target's own view, not a consent screen for the admin's session.
      if (status.impersonator) return;
      if (status.global_consent_accepted) return;
      const next = pathname ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/consent${next}`);
    });

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return null;
}
