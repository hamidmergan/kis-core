"use client";

import { Suspense, useEffect, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import LecturerView from "./_components/LecturerView";
import StudentView from "./_components/StudentView";

export default function KiTutorPage() {
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => setRole(s.role ?? "lecturer"));
  }, []);

  return (
    <ProtectedRoute>
      {role !== null && (role === "lecturer" ? <LecturerView /> : <Suspense><StudentView /></Suspense>)}
    </ProtectedRoute>
  );
}
