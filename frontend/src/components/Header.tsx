"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <h1 className="text-xl font-bold text-[#0066cc]">
        <Link href="/" aria-label="Zur Startseite">
          KIS
        </Link>
      </h1>
      {showLogout && (
        <div className="flex items-center gap-2">
          <JobsPanel />
          {isAdmin && (
            <Link
              href="/admin"
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            >
              Admin
            </Link>
          )}
          <button
            onClick={handleLogout}
            aria-label="Abmelden"
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
          >
            Abmelden
          </button>
        </div>
      )}
    </header>
  );
}
