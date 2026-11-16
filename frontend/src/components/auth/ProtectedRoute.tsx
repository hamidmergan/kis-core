"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import Spinner from "@/components/ui/Spinner";
import { isReturnPath, redirectFor } from "./_routeGuard";

export { isReturnPath };

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      const ziel = redirectFor(status, pathname);
      if (ziel) router.replace(ziel);
      else setAuthenticated(true);
      setLoading(false);
    });
  }, [router, pathname]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <Spinner size="lg" />
      </div>
    );
  }
  if (!authenticated) return null;
  return <>{children}</>;
}
