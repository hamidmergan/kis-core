"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { checkAuthStatus } from "@/lib/auth";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      if (!status.authenticated) {
        router.replace("/login");
      } else {
        setAuthenticated(true);
      }
      setLoading(false);
    });
  }, [router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066cc]" />
      </div>
    );
  }

  if (!authenticated) {
    return null;
  }

  return <>{children}</>;
}
