"use client";

import { useEffect, useState } from "react";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS } from "@/lib/permissions";
import type { UserPermissions, SystemRole } from "@/types";

export interface PermissionsState {
  loaded: boolean;
  permissions: UserPermissions;
  role: SystemRole | undefined;
}

export function usePermissions(): PermissionsState {
  const [state, setState] = useState<PermissionsState>({
    loaded: false,
    permissions: EMPTY_PERMS,
    role: undefined,
  });

  useEffect(() => {
    let cancelled = false;
    checkAuthStatus().then((status) => {
      if (cancelled) return;
      setState({
        loaded: true,
        permissions: status.permissions ?? EMPTY_PERMS,
        role: status.role,
      });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
