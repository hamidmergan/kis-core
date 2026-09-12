"use client";

import { Suspense, useEffect, useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS, PERM, hasPerm } from "@/lib/permissions";
import { enabledToolKeys, homeTargets } from "@/lib/modules";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import type { AuthStatus } from "@/types";
import WorkspaceHome from "./_components/WorkspaceHome";
import WelcomeModal from "./_components/WelcomeModal";

/** The module list. Students land here straight from "/", everyone else comes from the tiles. */
export default function WorkspaceListPage() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const { loaded: toolsLoaded, tools: enabledTools } = useEnabledTools();

  useEffect(() => {
    checkAuthStatus().then(setAuth);
  }, []);

  const perms = auth?.permissions ?? EMPTY_PERMS;
  // Only who lands here directly gets greeted, the tile page already did it for everyone else.
  const showGreeting =
    !!auth && toolsLoaded && homeTargets(auth.modules, perms, enabledToolKeys(enabledTools)).length === 1;

  return (
    <ProtectedRoute>
      {/* Impersonation shows the target account's own view, not an onboarding dialog for the admin's session. */}
      {auth && !auth.impersonator && hasPerm(perms, PERM.generalWelcome) && <WelcomeModal userId={auth.user_id} />}
      {auth && toolsLoaded && (
        <Suspense>
          <WorkspaceHome
            canCreate={!!perms.allow_workspace_create}
            firstName={auth.display_name?.split(" ")[0] ?? auth.username ?? ""}
            languageInvite={hasPerm(perms, PERM.aiaLanguageLevel)}
            showGreeting={showGreeting}
          />
        </Suspense>
      )}
    </ProtectedRoute>
  );
}
