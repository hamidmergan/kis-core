"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SignOut, UserCircleGear, House, Toolbox } from "@phosphor-icons/react";
import { checkAuthStatus, logout } from "@/lib/auth";
import JobsPanel from "@/components/JobsPanel";

interface HeaderProps {
  showLogout?: boolean;
}

export default function Header({ showLogout = false }: HeaderProps) {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    if (!showLogout) return;
    checkAuthStatus().then((s) => {
      setIsAdmin(s.is_admin ?? false);
      setRole(s.role ?? "lecturer");
    });
  }, [showLogout]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header style={{ backgroundColor: "var(--kb)" }} className="py-3">
      <div className="max-w-5xl mx-auto px-4 flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Link
            href="/ki-tutor"
            aria-label="Zur Startseite"
            className="text-white hover:opacity-80 transition-opacity"
          >
            KIS
          </Link>
          {process.env.NODE_ENV === "development" && (
            <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: "#f59e0b", color: "#000" }}>
              DEV
            </span>
          )}
        </h1>

        {showLogout && (
          <div className="flex items-center gap-1.5">
            <JobsPanel />

            {role !== "student" && (
              <Link
                href="/tools"
                className="flex items-center justify-center w-8 h-8 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Tools"
                title="Tools"
              >
                <Toolbox size={18} weight="bold" />
              </Link>
            )}

            <Link
              href="/ki-tutor"
              aria-label="Zur Übersicht"
              className="flex items-center justify-center w-8 h-8 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <House size={18} weight="bold" />
            </Link>

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
      </div>
    </header>
  );
}
