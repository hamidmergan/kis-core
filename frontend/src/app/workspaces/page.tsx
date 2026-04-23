"use client";

import { Suspense, useEffect, useState } from "react";
import Header from "@/components/layout/Header";
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
      <Header showLogout />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
        {role !== null && (role === "lecturer" ? <LecturerView /> : <Suspense><StudentView /></Suspense>)}
      </div>
    </ProtectedRoute>
  );
}
