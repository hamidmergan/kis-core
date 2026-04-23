"use client";

import { useEffect, useState } from "react";
import { checkAuthStatus } from "@/lib/auth";

export function useIsAdmin() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    checkAuthStatus()
      .then((status) => setIsAdmin(!!status.is_admin))
      .finally(() => setLoaded(true));
  }, []);

  return { isAdmin, loaded };
}
