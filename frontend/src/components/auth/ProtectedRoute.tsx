"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "@/i18n/navigation";
import { checkAuthStatus } from "@/lib/auth";
import Spinner from "@/components/ui/Spinner";
import { EMPTY_PERMS, PERM, hasPerm } from "@/lib/permissions";

const TOOL_KEY_BY_SLUG: Record<string, string> = {
  translate: "translation",
  interpreter: "interpreter",
  tts: "tts",
  stt: "transcription",
  image: "image",
  summarize: "summary",
  screencast: "screencast",
  podcast: "podcast",
  praesentation: "praesentation",
  glossary: "glossary",
};

function toolKeyFromPath(pathname: string | null): string | null {
  if (!pathname) return null;
  const segs = pathname.split("/").filter(Boolean);
  const idx = segs.indexOf("tools");
  if (idx === -1) return null;
  const slug = segs[idx + 1];
  return slug ? TOOL_KEY_BY_SLUG[slug] ?? null : null;
}

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      if (!status.authenticated) {
        // An expired access says so on the login page instead of landing there mute.
        router.replace(status.reason === "access_expired" ? "/login?expired=1" : "/login");
        setLoading(false);
        return;
      }
      const perms = status.permissions ?? EMPTY_PERMS;
      // The list at /workspace and every module below it belong to the assistant.
      const isWorkspacePath = pathname === "/workspace" || pathname?.startsWith("/workspace/");
      const isAdminPath = pathname?.startsWith("/admin");
      const isManualPath = pathname?.startsWith("/manual");
      const isToolPath = pathname?.startsWith("/tools/");
      const isJobsPath = pathname?.startsWith("/my-jobs");
      const isCalendarPath = pathname === "/calendar" || pathname?.startsWith("/calendar/");

      // The calendar is pure assistant, a missing modules field means an older server.
      if (isCalendarPath && !(status.modules ?? ["aia", "tools"]).includes("aia")) {
        router.replace("/");
        setLoading(false);
        return;
      }
      if (isAdminPath && !perms.allow_admin_panel) {
        router.replace("/");
        setLoading(false);
        return;
      }
      if (isManualPath && !hasPerm(perms, PERM.manual)) {
        router.replace("/");
        setLoading(false);
        return;
      }
      if (isToolPath) {
        const key = toolKeyFromPath(pathname);
        if (key && !perms.tools.includes(key)) {
          router.replace("/");
          setLoading(false);
          return;
        }
      }
      // Jobs only come from tools, without a tool permission there is nothing to see.
      if (isJobsPath && perms.tools.length === 0) {
        router.replace("/");
        setLoading(false);
        return;
      }
      if (isWorkspacePath && !perms.allow_aia) {
        router.replace("/");
        setLoading(false);
        return;
      }
      setAuthenticated(true);
      setLoading(false);
    });
  }, [router, pathname]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <Spinner size="lg" />
      </div>
    );
  }
  if (!authenticated) return null;
  return <>{children}</>;
}
