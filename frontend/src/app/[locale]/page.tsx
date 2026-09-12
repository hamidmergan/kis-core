"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import LockedNotice from "@/components/auth/LockedNotice";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS, PERM, hasPerm } from "@/lib/permissions";
import { homeTargets, enabledToolKeys, type HomeTarget } from "@/lib/modules";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import type { AuthStatus } from "@/types";
import StartOverview from "./_components/StartOverview";
import WelcomeModal from "./workspace/_components/WelcomeModal";

interface HomeState {
  targets: HomeTarget[];
  firstName: string;
}

export default function HomePage() {
  return (
    <ProtectedRoute>
      {/* The query string is only readable inside a Suspense boundary. */}
      <Suspense>
        <HomeRouter />
      </Suspense>
    </ProtectedRoute>
  );
}

/** One place to go means a straight redirect, more than one means the tiles. */
function HomeRouter() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const { loaded: toolsLoaded, tools: enabledTools } = useEnabledTools();
  const [state, setState] = useState<HomeState | null>(null);

  useEffect(() => {
    checkAuthStatus().then(setAuth);
  }, []);

  useEffect(() => {
    if (!auth || !toolsLoaded) return;
    const perms = auth.permissions ?? EMPTY_PERMS;
    setState({
      targets: homeTargets(auth.modules, perms, enabledToolKeys(enabledTools)),
      firstName: auth.display_name?.split(" ")[0] ?? auth.username ?? "",
    });
  }, [auth, toolsLoaded, enabledTools]);

  const code = searchParams.get("code");
  const hasAia = state?.targets.some((z) => z.kind === "aia") ?? false;
  // Old invitation links still point here, the enrolment card lives on the module list now.
  const weiter =
    state === null
      ? null
      : code && hasAia
        ? `/workspace?code=${encodeURIComponent(code)}`
        : state.targets.length === 1
          ? state.targets[0].href
          : null;

  useEffect(() => {
    if (weiter) router.replace(weiter);
  }, [weiter, router]);

  if (state === null || weiter) return null;

  return (
    <>
      {/* Impersonation shows the target account's own view, not an onboarding dialog for the admin's session. */}
      {!auth?.impersonator && hasPerm(auth?.permissions, PERM.generalWelcome) && (
        <WelcomeModal userId={auth?.user_id} />
      )}
      {state.targets.length === 0 ? (
        <div className="px-4 sm:px-6 md:px-8 pt-10 pb-20">
          <div className="max-w-2xl mx-auto">
            <LockedNotice variant="aia" />
          </div>
        </div>
      ) : (
        <StartOverview firstName={state.firstName} targets={state.targets} />
      )}
    </>
  );
}
