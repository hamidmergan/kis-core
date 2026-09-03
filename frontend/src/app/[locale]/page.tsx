"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import LockedNotice from "@/components/auth/LockedNotice";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS, PERM, hasPerm } from "@/lib/permissions";
import { pickHomeTarget, enabledToolKeys, type HomeTarget } from "@/lib/modules";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import type { AuthStatus } from "@/types";
import WorkspaceHome from "./workspace/_components/WorkspaceHome";
import WelcomeModal from "./workspace/_components/WelcomeModal";
import InternationalPromptModal from "./workspace/_components/InternationalPromptModal";

interface HomeState {
  target: HomeTarget;
  canCreate: boolean;
  firstName: string;
}

export default function HomePage() {
  const router = useRouter();
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const { loaded: toolsLoaded, tools: enabledTools } = useEnabledTools();
  const [state, setState] = useState<HomeState | null>(null);
  // The welcome dialog goes first, the start question waits until it is settled.
  const [welcomeSettled, setWelcomeSettled] = useState(false);

  useEffect(() => {
    checkAuthStatus().then(setAuth);
  }, []);

  useEffect(() => {
    if (!auth || !toolsLoaded) return;
    const perms = auth.permissions ?? EMPTY_PERMS;
    const enabledKeys = enabledToolKeys(enabledTools);
    setState({
      target: pickHomeTarget(auth.modules, perms, enabledKeys),
      canCreate: !!perms.allow_workspace_create,
      firstName: auth.display_name?.split(" ")[0] ?? auth.username ?? "",
    });
  }, [auth, toolsLoaded, enabledTools]);

  useEffect(() => {
    if (state?.target.kind === "tool") router.replace(state.target.href);
  }, [state, router]);

  return (
    <ProtectedRoute>
      {/* Impersonation shows the target account's own view, not an onboarding dialog for the admin's session. */}
      {!auth?.impersonator && hasPerm(auth?.permissions, PERM.generalWelcome) && (
        <WelcomeModal userId={auth?.user_id} onSettled={() => setWelcomeSettled(true)} />
      )}
      {auth && !auth.impersonator && hasPerm(auth.permissions, PERM.aiaUse) && (
        <InternationalPromptModal
          userId={auth.user_id}
          role={auth.role}
          blocked={hasPerm(auth.permissions, PERM.generalWelcome) && !welcomeSettled}
        />
      )}
      {state === null || state.target.kind === "tool" ? null : state.target.kind === "aia" ? (
        <Suspense>
          <WorkspaceHome canCreate={state.canCreate} firstName={state.firstName} />
        </Suspense>
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
