"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { checkAuthStatus } from "@/lib/auth";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      if (!status.authenticated) {
        router.replace("/");
      } else {
        const role = status.role ?? "lecturer";
        const isKiTutor = pathname?.startsWith("/ki-tutor");
        if (role === "student" && !isKiTutor) {
          router.replace("/ki-tutor");
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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#004261]" />
      </div>
    );
  }

  if (!authenticated) {
    return null;
  }

  return <>{children}</>;
}
