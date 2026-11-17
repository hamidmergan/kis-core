"use client";

import { useTranslations } from "next-intl";
import { Lock } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { Link } from "@/i18n/navigation";

/** The course is inactive, the page says so and offers the way back. */
export function LockedScreen() {
  const tClosed = useTranslations("workspace.detail.closed");
  return (
    <ProtectedRoute>
      <div className="aia-scale flex flex-col overflow-hidden viewport-shell">
        <Header showLogout />
        <div className="flex-1 flex items-center justify-center px-6">
          <div
            className="max-w-md w-full rounded-xl p-8 text-center"
            style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
          >
            <Lock size={32} weight="fill" className="mx-auto mb-4" style={{ color: "var(--muted)" }} />
            <h1 className="text-lg font-semibold mb-2" style={{ color: "var(--foreground)" }}>
              {tClosed("title")}
            </h1>
            <p className="text-sm mb-6" style={{ color: "var(--muted)" }}>
              {tClosed("text")}
            </p>
            <Link href="/workspace" className="btn-primary inline-block px-6 py-2.5 rounded-lg text-sm font-medium">
              {tClosed("back")}
            </Link>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}

/** Shown until the workspace, its messages and its settings are loaded. */
export function LoadingScreen() {
  return (
    <ProtectedRoute>
      <div className="aia-scale flex flex-col overflow-hidden viewport-shell">
        <div className="flex-1 flex items-center justify-center">
          <Spinner size="lg" />
        </div>
      </div>
    </ProtectedRoute>
  );
}
