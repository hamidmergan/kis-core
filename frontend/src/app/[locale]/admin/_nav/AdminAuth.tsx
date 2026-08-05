"use client";

/**
 * Zugangsprüfung einmal fürs ganze Layout.
 *
 * Vorher stand sie in page.tsx und lief bei jedem Tab-Wechsel mit, weil alles
 * eine Komponente war. Jetzt hängt sie am Layout, das über allen Seiten steht,
 * und die eigene Adresse braucht sie nur noch zum Weiterleiten.
 *
 * Die Adresse des Admins geben wir weiter, weil die Whitelist sie braucht, um
 * den eigenen Eintrag zu kennzeichnen.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";

const AdminEmailCtx = createContext<string>("");

export function useAdminEmail(): string {
  return useContext(AdminEmailCtx);
}

export default function AdminAuth({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    checkAuthStatus().then((s) => {
      if (!s.authenticated) { router.push("/login"); return; }
      if (!s.is_admin) { router.push("/"); return; }
      setEmail(s.email ?? "");
    });
  }, [router]);

  // Nichts rendern, solange unklar ist, ob jemand hier sein darf. Sonst blitzt
  // der Adminbereich kurz auf, bevor die Weiterleitung greift.
  if (email === null) return null;

  return <AdminEmailCtx.Provider value={email}>{children}</AdminEmailCtx.Provider>;
}
