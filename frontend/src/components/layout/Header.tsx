"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SignOut, UserCircleGear, House } from "@phosphor-icons/react";
import { checkAuthStatus, logout } from "@/lib/auth";
import JobsPanel from "@/components/jobs/JobsPanel";

interface HeaderProps {
  showLogout?: boolean;
}

export default function Header({ showLogout = false }: HeaderProps) {
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
      <div className="max-w-5xl mx-auto px-4 flex items-center justify-between">
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
          <div className="flex items-center gap-1.5">
            <Link
              href="/workspaces"
              aria-label="Zur Übersicht"
              className="flex items-center justify-center w-10 h-10 sm:w-9 sm:h-9 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <House size={18} weight="bold" />
            </Link>

            <JobsPanel />

            {isAdmin && (
              <Link
                href="/admin"
                aria-label="Admin"
                className="flex items-center justify-center w-10 h-10 sm:w-9 sm:h-9 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
              >
                <UserCircleGear size={18} weight="bold" />
              </Link>
            )}

            <button
              onClick={handleLogout}
              aria-label="Abmelden"
              className="flex items-center justify-center w-10 h-10 sm:w-9 sm:h-9 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <SignOut size={17} weight="bold" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
