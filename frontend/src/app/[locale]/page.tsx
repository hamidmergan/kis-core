"use client";

import { Suspense, useEffect, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import LecturerView from "./workspace/_components/LecturerView";
import StudentView from "./workspace/_components/StudentView";

export default function HomePage() {
  // null = still loading. true = staff/admin (can create workspaces). false = user role.
  const [canCreate, setCanCreate] = useState<boolean | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => {
      setCanCreate(!!s.permissions?.allow_workspace_create);
    });
  }, []);

  return (
    <ProtectedRoute>
      {canCreate === null ? null : (
        canCreate ? <LecturerView /> : <Suspense><StudentView /></Suspense>
      )}
    </ProtectedRoute>
  );
}
