"use client";

import { Suspense, useEffect, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import LockedNotice from "@/components/auth/LockedNotice";
import { checkAuthStatus } from "@/lib/auth";
import LecturerView from "./workspace/_components/LecturerView";
import StudentView from "./workspace/_components/StudentView";

type HomeView = "lecturer" | "student" | "tools-only";

export default function HomePage() {
  const [view, setView] = useState<HomeView | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => {
      const perms = s.permissions;
      if (perms?.allow_workspace_create) setView("lecturer");
      else if (perms?.allow_aia) setView("student");
      else setView("tools-only");
    });
  }, []);

  return (
    <ProtectedRoute>
      {view === null ? null : view === "lecturer" ? (
        <LecturerView />
      ) : view === "student" ? (
        <Suspense><StudentView /></Suspense>
      ) : (
        <div className="px-4 sm:px-6 md:px-8 pt-10 pb-20">
          <div className="max-w-2xl mx-auto">
            <LockedNotice variant="aia" />
          </div>
        </div>
      )}
    </ProtectedRoute>
  );
}
