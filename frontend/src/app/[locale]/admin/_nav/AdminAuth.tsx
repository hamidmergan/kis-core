"use client";

/**
 * Zugangsprüfung einmal fürs ganze Layout.
 *
 * Vorher stand sie in page.tsx und lief bei jedem Tab-Wechsel mit, weil alles
 * eine Komponente war. Jetzt hängt sie am Layout, das über allen Seiten steht,
 * und die eigene Adresse braucht sie nur noch zum Weiterleiten.
 *
 * Sie prüft nicht mehr "ist Administrator", sondern "darf hier irgendetwas".
 * Der Bereich zerfällt in Seiten, die einzeln vergeben werden, und eine Rolle,
 * die nur das Sprachniveau pflegt, gehört genauso hierher wie der Admin.
 *
 * Die Adresse des Admins geben wir weiter, weil die Whitelist sie braucht, um
 * den eigenen Eintrag zu kennzeichnen. Die Rechte gibt sie weiter, weil
 * Seitenleiste und Seite selbst danach filtern.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS, isFullAdmin } from "@/lib/permissions";
import type { UserPermissions } from "@/types";

const AdminEmailCtx = createContext<string>("");
const AdminPermsCtx = createContext<UserPermissions>(EMPTY_PERMS);

export function useAdminEmail(): string {
  return useContext(AdminEmailCtx);
}

/** Die Rechte der angemeldeten Person. Nie undefined, im Zweifel leer. */
export function useAdminPerms(): UserPermissions {
  return useContext(AdminPermsCtx);
}

/** Heißt der Bereich für diese Person "Administration" oder "Einstellungen"? */
export function useIsFullAdmin(): boolean {
  return isFullAdmin(useAdminPerms());
}

export default function AdminAuth({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ email: string; perms: UserPermissions } | null>(null);
  const router = useRouter();

  useEffect(() => {
    checkAuthStatus().then((s) => {
      if (!s.authenticated) { router.push("/login"); return; }
      const perms = s.permissions ?? EMPTY_PERMS;
      // allow_admin_panel heißt seit der Rechtematrix: mindestens ein Recht aus
      // der Gruppe Einstellungen. Wer keines hat, hat hier nichts zu suchen.
      if (!perms.allow_admin_panel) { router.push("/"); return; }
      setState({ email: s.email ?? "", perms });
    });
  }, [router]);

  // Nichts rendern, solange unklar ist, ob jemand hier sein darf. Sonst blitzt
  // der Adminbereich kurz auf, bevor die Weiterleitung greift.
  if (state === null) return null;

  return (
    <AdminEmailCtx.Provider value={state.email}>
      <AdminPermsCtx.Provider value={state.perms}>{children}</AdminPermsCtx.Provider>
    </AdminEmailCtx.Provider>
  );
}
