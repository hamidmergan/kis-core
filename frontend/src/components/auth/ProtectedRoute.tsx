"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { checkAuthStatus } from "@/lib/auth";
import Spinner from "@/components/ui/Spinner";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      if (!status.authenticated) {
        router.replace("/login");
      } else {
        const role = status.role ?? "lecturer";
        const isKiTutor = pathname === "/" || pathname?.startsWith("/workspace/");
        if (role === "student" && !isKiTutor) {
          router.replace("/");
        } else {
          setAuthenticated(true);
        }
      }
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

  if (!authenticated) {
    return null;
  }

  return <>{children}</>;
}
