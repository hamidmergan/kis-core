"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import LockedNotice from "@/components/auth/LockedNotice";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS } from "@/lib/permissions";
import { pickHomeTarget, type HomeTarget } from "@/lib/modules";
import WorkspaceHome from "./workspace/_components/WorkspaceHome";
import HomeNotice from "./workspace/_components/HomeNotice";

interface HomeState {
  target: HomeTarget;
  canCreate: boolean;
  firstName: string;
}

export default function HomePage() {
  const router = useRouter();
  const [state, setState] = useState<HomeState | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => {
      const perms = s.permissions ?? EMPTY_PERMS;
      setState({
        target: pickHomeTarget(s.modules, perms),
        canCreate: !!perms.allow_workspace_create,
        firstName: s.display_name?.split(" ")[0] ?? s.username ?? "",
      });
    });
  }, []);

  useEffect(() => {
    if (state?.target.kind === "tool") router.replace(state.target.href);
  }, [state, router]);

  return (
    <ProtectedRoute>
      {state === null || state.target.kind === "tool" ? null : state.target.kind === "aia" ? (
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
