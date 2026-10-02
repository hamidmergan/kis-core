"use client";

/** One access check for the whole layout, it asks for permissions instead of rank. */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS } from "@/lib/permissions";
import type { UserPermissions } from "@/types";

const AdminEmailCtx = createContext<string>("");
const AdminPermsCtx = createContext<UserPermissions>(EMPTY_PERMS);

export function useAdminEmail(): string {
  return useContext(AdminEmailCtx);
}

/** The permissions of the logged-in person, never undefined, empty when in doubt. */
export function useAdminPerms(): UserPermissions {
  return useContext(AdminPermsCtx);
}

export default function AdminAuth({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ email: string; perms: UserPermissions } | null>(null);
  const router = useRouter();

  useEffect(() => {
    checkAuthStatus().then((s) => {
      if (!s.authenticated) { router.push("/login"); return; }
      const perms = s.permissions ?? EMPTY_PERMS;
      // Whoever holds not a single settings permission has no business here.
      if (!perms.allow_admin_panel) { router.push("/services"); return; }
      setState({ email: s.email ?? "", perms });
    });
  }, [router]);

  // Render nothing while it is unclear whether someone may be here.
  if (state === null) return null;

  return (
    <AdminEmailCtx.Provider value={state.email}>
      <AdminPermsCtx.Provider value={state.perms}>{children}</AdminPermsCtx.Provider>
    </AdminEmailCtx.Provider>
  );
}
