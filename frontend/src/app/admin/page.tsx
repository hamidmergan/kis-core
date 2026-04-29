"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { checkAuthStatus } from "@/lib/auth";
import PendingTab from "./_components/PendingTab";
import WhitelistTab from "./_components/WhitelistTab";
import UsersTab from "./_components/UsersTab";
import StatsTab from "./_components/StatsTab";
import KiTutorTab from "./_components/KiTutorTab";
import JobsTab from "./_components/JobsTab";
import SettingsTab from "./_components/SettingsTab";
import PromptsTab from "./_components/PromptsTab";
import QuotaTab from "./_components/QuotaTab";

type Tab = "pending" | "whitelist" | "users" | "jobs" | "stats" | "ki-tutor" | "settings" | "prompts" | "quota";

const TABS: { key: Tab; label: string }[] = [
  { key: "settings", label: "Einstellungen" },
  { key: "prompts", label: "Prompts" },
  { key: "pending", label: "Ausstehend" },
  { key: "whitelist", label: "Whitelist" },
  { key: "users", label: "Alle User" },
  { key: "jobs", label: "Alle Jobs" },
  { key: "stats", label: "Statistiken" },
  { key: "ki-tutor", label: "KI-Assistent" },
];

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("settings");
  const [checking, setChecking] = useState(true);
  const [adminEmail, setAdminEmail] = useState("");
  const [quotaTargetId, setQuotaTargetId] = useState<number | null>(null);
  const router = useRouter();

  const openQuotaForUser = (userId: number) => {
    setQuotaTargetId(userId);
    setTab("quota");
  };

  useEffect(() => {
    checkAuthStatus().then((s) => {
      if (!s.authenticated) {
        router.push("/login");
        return;
      }
      if (!s.is_admin) {
        router.push("/");
        return;
      }
      setAdminEmail(s.email ?? "");
      setChecking(false);
    });
  }, [router]);

  if (checking) return null;

  return (
    <>
      <main className="max-w-4xl mx-auto px-4 py-8">
        <h2 className="text-lg font-semibold mb-6">Admin-Bereich</h2>

        <div className="flex gap-1 border-b border-border-soft mb-6 overflow-x-auto scrollbar-none">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0 ${
                tab === t.key
                  ? "border-kb text-kb"
                  : "border-transparent text-muted hover:text-foreground-soft"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "pending" && <PendingTab />}
        {tab === "whitelist" && <WhitelistTab adminEmail={adminEmail} />}
        {tab === "users" && <UsersTab onOpenQuota={openQuotaForUser} />}
        {tab === "jobs" && <JobsTab />}
        {tab === "stats" && <StatsTab />}
        {tab === "ki-tutor" && <KiTutorTab />}
        {tab === "settings" && <SettingsTab />}
        {tab === "prompts" && <PromptsTab />}
        {tab === "quota" && (
          <QuotaTab
            targetUserId={quotaTargetId}
            onConsumed={() => setQuotaTargetId(null)}
            onBack={() => setTab("users")}
          />
        )}
      </main>
    </>
  );
}
