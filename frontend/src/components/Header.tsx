"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SignOut, UserCircleGear } from "@phosphor-icons/react";
import { checkAuthStatus, logout } from "@/lib/auth";
import JobsPanel from "@/components/JobsPanel";

interface HeaderProps {
  showLogout?: boolean;
}

export default function Header({ showLogout = false }: HeaderProps) {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (!showLogout) return;
    checkAuthStatus().then((s) => setIsAdmin(s.is_admin ?? false));
  }, [showLogout]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header
      style={{ backgroundColor: "#004261" }}
      className="px-5 py-3 flex items-center justify-between"
    >
      <h1 className="text-lg font-semibold tracking-tight">
        <Link
          href="/"
          aria-label="Zur Startseite"
          className="text-white hover:opacity-80 transition-opacity"
        >
          KIS
        </Link>
      </h1>

      {showLogout && (
        <div className="flex items-center gap-1.5">
          <JobsPanel />

          {isAdmin && (
            <Link
              href="/admin"
              aria-label="Admin"
              className="flex items-center justify-center w-8 h-8 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <UserCircleGear size={18} weight="bold" />
            </Link>
          )}

          <button
            onClick={handleLogout}
            aria-label="Abmelden"
            className="flex items-center justify-center w-8 h-8 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
          >
            <SignOut size={17} weight="bold" />
          </button>
        </div>
      )}
    </header>
  );
}
