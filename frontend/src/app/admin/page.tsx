"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bird,
  ChartBar,
  ChartLineUp,
  CheckCircle,
  GearSix,
  HourglassMedium,
  Lightning,
  List,
  ListMagnifyingGlass,
  NotePencil,
  Sparkle,
  Toolbox,
  Users,
  X,
} from "@phosphor-icons/react";
import { checkAuthStatus } from "@/lib/auth";
import PendingTab from "./_components/PendingTab";
import WhitelistTab from "./_components/WhitelistTab";
import UsersTab from "./_components/UsersTab";
import StatsTab from "./_components/StatsTab";
import KiTutorTab from "./_components/KiTutorTab";
import JobsTab from "./_components/JobsTab";
import SettingsTab, { type SettingsSection } from "./_components/SettingsTab";
import PromptsTab from "./_components/PromptsTab";
import QuotaTab from "./_components/QuotaTab";
import HildeTab from "./_components/HildeTab";
import ToolsTab from "./_components/ToolsTab";
import SystemInfoTab from "./_components/SystemInfoTab";

type Tab =
  | "system"
  | "ki"
  | "prompts"
  | "pending"
  | "whitelist"
  | "users"
  | "tools"
  | "jobs"
  | "stats"
  | "ki-stats"
  | "limits"
  | "hilde"
  | "quota";

interface NavItem {
  key: Tab;
  label: string;
  icon: React.ReactNode;
  hasSubs?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const ICON_PROPS = { size: 18, weight: "bold" as const };

const NAV: NavGroup[] = [
  {
    label: "Konfiguration",
    items: [
      { key: "system", label: "System", icon: <GearSix {...ICON_PROPS} /> },
      { key: "ki", label: "KI", icon: <Sparkle {...ICON_PROPS} />, hasSubs: true },
      { key: "prompts", label: "Prompts", icon: <NotePencil {...ICON_PROPS} /> },
    ],
  },
  {
    label: "Nutzer",
    items: [
      { key: "pending", label: "Ausstehend", icon: <HourglassMedium {...ICON_PROPS} /> },
      { key: "whitelist", label: "Whitelist", icon: <CheckCircle {...ICON_PROPS} /> },
      { key: "users", label: "Alle User", icon: <Users {...ICON_PROPS} /> },
    ],
  },
  {
    label: "Tools",
    items: [
      { key: "tools", label: "Tools", icon: <Toolbox {...ICON_PROPS} /> },
      { key: "jobs", label: "Alle Jobs", icon: <Lightning {...ICON_PROPS} /> },
    ],
  },
  {
    label: "Betrieb",
    items: [
      { key: "stats", label: "Jobs Statistiken", icon: <ChartBar {...ICON_PROPS} /> },
      { key: "ki-stats", label: "KI-Assistent Statistiken", icon: <ChartLineUp {...ICON_PROPS} /> },
      { key: "limits", label: "Systemwerte", icon: <ListMagnifyingGlass {...ICON_PROPS} /> },
    ],
  },
  {
    label: "Spielwiese",
    items: [{ key: "hilde", label: "Maskottchen", icon: <Bird {...ICON_PROPS} /> }],
  },
];

const KI_SUBS: { key: Exclude<SettingsSection, "system">; label: string }[] = [
  { key: "speech", label: "Sprache" },
  { key: "images", label: "Bilder" },
  { key: "embedding", label: "Embedding" },
  { key: "llm", label: "LLM" },
];

function flatItems(): NavItem[] {
  return NAV.flatMap((g) => g.items);
}

function findItem(key: Tab): NavItem | undefined {
  return flatItems().find((i) => i.key === key);
}

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("system");
  const [kiSection, setKiSection] = useState<Exclude<SettingsSection, "system">>("speech");
  const [checking, setChecking] = useState(true);
  const [adminEmail, setAdminEmail] = useState("");
  const [quotaTargetId, setQuotaTargetId] = useState<number | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
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

  const currentItem = findItem(tab);
  const currentLabel =
    tab === "ki" ? `KI · ${KI_SUBS.find((s) => s.key === kiSection)?.label ?? ""}` : currentItem?.label ?? "";

  const selectTab = (k: Tab) => {
    setTab(k);
    setMobileNavOpen(false);
  };

  return (
    <div className="flex flex-col md:flex-row min-h-[calc(100vh-4rem)]">
      {/* Mobile menu button + crumb bar */}
      <div className="md:hidden flex items-center gap-3 px-4 h-12 border-b border-border-soft bg-white sticky top-0 z-20">
        <button
          onClick={() => setMobileNavOpen(true)}
          className="w-9 h-9 rounded-lg bg-surface border-2 border-transparent flex items-center justify-center text-muted transition-colors hover:border-kb hover:text-kb"
          aria-label="Menü öffnen"
        >
          <List size={18} weight="bold" />
        </button>
        <div className="text-sm font-medium text-foreground-soft truncate">{currentLabel}</div>
      </div>

      {/* Scrim for mobile drawer */}
      {mobileNavOpen && (
        <button
          onClick={() => setMobileNavOpen(false)}
          aria-label="Menü schließen"
          className="md:hidden fixed inset-0 top-16 bg-black/40 z-30"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`bg-surface border-r border-border-soft p-3 flex flex-col gap-0.5 overflow-y-auto
          fixed md:sticky top-16 md:top-16 left-0 bottom-0 md:bottom-auto
          h-[calc(100vh-4rem)] md:h-[calc(100vh-4rem)]
          w-72 md:w-60 z-40
          shadow-xl md:shadow-none
          transition-transform duration-200
          ${mobileNavOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
      >
        <div className="md:hidden flex items-center justify-between px-2 pt-1 pb-2">
          <span className="text-sm font-semibold">Admin</span>
          <button
            onClick={() => setMobileNavOpen(false)}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-muted transition-colors hover:bg-surface-dim hover:text-kb"
            aria-label="Schließen"
          >
            <X size={16} weight="bold" />
          </button>
        </div>

        {NAV.map((group) => (
          <div key={group.label}>
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted px-3.5 pt-3 pb-1.5">
              {group.label}
            </div>
            {group.items.map((item) => {
              const active = tab === item.key;
              return (
                <div key={item.key}>
                  <button
                    onClick={() => selectTab(item.key)}
                    className={`group w-full flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-sm font-medium text-left transition-colors ${
                      active
                        ? "bg-kb/8 text-kb font-semibold"
                        : "text-foreground-soft hover:bg-surface-dim hover:text-kb"
                    }`}
                    style={active ? { backgroundColor: "rgba(0, 66, 97, 0.08)" } : undefined}
                  >
                    <span
                      className={`transition-colors ${
                        active ? "text-kb" : "text-muted group-hover:text-kb"
                      }`}
                    >
                      {item.icon}
                    </span>
                    <span className="flex-1">{item.label}</span>
                    {item.hasSubs && (
                      <span
                        className={`text-xs transition-all ${
                          active ? "rotate-90 text-kb" : "text-muted group-hover:text-kb"
                        }`}
                      >
                        ›
                      </span>
                    )}
                  </button>
                  {item.hasSubs && active && (
                    <div className="ml-7 my-1 border-l border-border-soft flex flex-col gap-0.5 pl-1">
                      {KI_SUBS.map((sub) => {
                        const subActive = kiSection === sub.key;
                        return (
                          <button
                            key={sub.key}
                            onClick={() => {
                              setKiSection(sub.key);
                              setMobileNavOpen(false);
                            }}
                            className={`px-3 py-1.5 rounded-md text-[13px] text-left transition-colors ${
                              subActive
                                ? "text-kb font-semibold"
                                : "text-muted hover:text-foreground-soft hover:bg-surface-dim"
                            }`}
                            style={subActive ? { backgroundColor: "rgba(0, 66, 97, 0.08)" } : undefined}
                          >
                            {sub.label}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 px-4 py-6 md:px-8 md:py-8 lg:px-10">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-lg font-semibold mb-6">{currentLabel}</h2>

          {tab === "system" && <SettingsTab section="system" />}
          {tab === "ki" && <SettingsTab section={kiSection} />}
          {tab === "prompts" && <PromptsTab />}
          {tab === "pending" && <PendingTab />}
          {tab === "whitelist" && <WhitelistTab adminEmail={adminEmail} />}
          {tab === "users" && <UsersTab onOpenQuota={openQuotaForUser} />}
          {tab === "tools" && <ToolsTab />}
          {tab === "jobs" && <JobsTab />}
          {tab === "stats" && <StatsTab />}
          {tab === "ki-stats" && <KiTutorTab />}
          {tab === "limits" && <SystemInfoTab />}
          {tab === "hilde" && <HildeTab />}
          {tab === "quota" && (
            <QuotaTab
              targetUserId={quotaTargetId}
              onConsumed={() => setQuotaTargetId(null)}
              onBack={() => setTab("users")}
            />
          )}
        </div>
      </main>
    </div>
  );
}
