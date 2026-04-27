"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarBlank, SignOut, UserCircleGear } from "@phosphor-icons/react";
import { checkAuthStatus, logout } from "@/lib/auth";
import JobsPanel from "@/components/jobs/JobsPanel";
import HeaderMobileMenu from "@/components/layout/HeaderMobileMenu";

interface HeaderProps {
  showLogout?: boolean;
  showToolsToggle?: boolean;
}

export default function Header({ showLogout = false, showToolsToggle = false }: HeaderProps) {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (!showLogout) return;
    checkAuthStatus().then((s) => {
      setIsAdmin(s.is_admin ?? false);
    });
  }, [showLogout]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header style={{ backgroundColor: "var(--kb)" }} className="py-3 hide-on-short">
      <div className="px-4 sm:px-6 flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Link
            href="/workspaces"
            aria-label="Zur Startseite"
            className="text-white hover:opacity-80 transition-opacity"
          >
            KIS
          </Link>
          {process.env.NODE_ENV === "development" && (
            <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: "#532bdd", color: "#fff" }}>
              DEV
            </span>
          )}
        </h1>

        {showLogout && (
          <>
            <div className="hidden sm:flex items-center gap-1.5">
              <Link
                href="/schedule"
                aria-label="Zeitplan"
                title="Zeitplan"
                className="flex items-center justify-center h-9 px-3 gap-1.5 rounded-full text-white/80 hover:text-white hover:bg-white/10 transition-colors"
              >
                <CalendarBlank size={17} weight="bold" />
                <span className="text-sm font-medium">Zeitplan</span>
              </Link>

              <JobsPanel />

              {isAdmin && (
                <Link
                  href="/admin"
                  aria-label="Admin"
                  title="Admin"
                  className="flex items-center justify-center h-9 px-3 gap-1.5 rounded-full text-white/80 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <UserCircleGear size={17} weight="bold" />
                  <span className="text-sm font-medium">Admin</span>
                </Link>
              )}

              <button
                onClick={handleLogout}
                aria-label="Abmelden"
                title="Abmelden"
                className="flex items-center justify-center h-9 px-3 gap-1.5 ml-1 rounded-full text-white/80 hover:text-white border border-white/25 hover:bg-white/10 transition-colors"
              >
                <SignOut size={17} weight="bold" />
                <span className="text-sm font-medium">Abmelden</span>
              </button>
            </div>

            <HeaderMobileMenu isAdmin={isAdmin} showToolsToggle={showToolsToggle} onLogout={handleLogout} />
          </>
        )}
      </div>
    </header>
  );
}
