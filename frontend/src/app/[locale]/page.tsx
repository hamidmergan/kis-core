"use client";

import { Suspense, useEffect, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import LockedNotice from "@/components/auth/LockedNotice";
import { checkAuthStatus } from "@/lib/auth";
import WorkspaceHome from "./workspace/_components/WorkspaceHome";
import HomeNotice from "./workspace/_components/HomeNotice";

interface HomeState {
  allowAia: boolean;
  canCreate: boolean;
  firstName: string;
}

export default function HomePage() {
  const [state, setState] = useState<HomeState | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => {
      setState({
        allowAia: !!s.permissions?.allow_aia,
        canCreate: !!s.permissions?.allow_workspace_create,
        firstName: s.display_name?.split(" ")[0] ?? s.username ?? "",
      });
    });
  }, []);

  return (
    <ProtectedRoute>
      {state === null ? null : state.allowAia ? (
        <Suspense>
          <WorkspaceHome canCreate={state.canCreate} firstName={state.firstName} />
        </Suspense>
      ) : (
        <div className="px-4 sm:px-6 md:px-8 pt-10 pb-20">
          <div className="max-w-2xl mx-auto">
            <HomeNotice />
            <LockedNotice variant="aia" />
          </div>
        </div>
      )}
    </ProtectedRoute>
  );
}
