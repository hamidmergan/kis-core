"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import {
  Bird,
  ChartBar,
  ChartLineUp,
  CheckCircle,
  GearSix,
  GraduationCap,
  HourglassMedium,
  IdentificationCard,
  Lightning,
  List,
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
import SettingsTab from "./_components/SettingsTab";
import ProvidersTab from "./_components/providers";
import PromptsTab from "./_components/PromptsTab";
import QuotaTab from "./_components/QuotaTab";
import HildeTab from "./_components/HildeTab";
import FrancisTab from "./_components/FrancisTab";
import ToolsTab from "./_components/ToolsTab";
import RolesTab from "./_components/RolesTab";
import LanguageDiagnosisCard from "./_components/LanguageDiagnosisCard";
import DiagnosisQuestionPlanCard from "./_components/DiagnosisQuestionPlanCard";
import DiagnosisGradingCard from "./_components/DiagnosisGradingCard";
import DiagnosisExamplesCard from "./_components/DiagnosisExamplesCard";
import DiagnosisAdaptiveBehaviorCard from "./_components/DiagnosisAdaptiveBehaviorCard";

type Tab =
  | "system"
  | "ki"
  | "prompts"
  | "diagnosis"
  | "pending"
  | "whitelist"
  | "users"
  | "roles"
  | "tools"
  | "jobs"
  | "stats"
  | "ki-stats"
  | "hilde"
  | "francis"
  | "quota";

interface NavItem {
  key: Tab;
  label: string;
  icon: React.ReactNode;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const ICON_PROPS = { size: 18, weight: "bold" as const };

export default function AdminPage() {
  const t = useTranslations("admin");
  const [tab, setTab] = useState<Tab>("system");
  const [checking, setChecking] = useState(true);
  const [adminEmail, setAdminEmail] = useState("");
  const [quotaTargetId, setQuotaTargetId] = useState<number | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const router = useRouter();

  const NAV: NavGroup[] = [
    {
      label: t("nav.configuration"),
      items: [
        { key: "system", label: t("nav.system"), icon: <GearSix {...ICON_PROPS} /> },
        { key: "ki", label: t("nav.ki"), icon: <Sparkle {...ICON_PROPS} /> },
        { key: "prompts", label: t("nav.prompts"), icon: <NotePencil {...ICON_PROPS} /> },
        {
          key: "diagnosis",
          label: t("nav.languageDiagnosis"),
          icon: <GraduationCap {...ICON_PROPS} />,
        },
      ],
    },
    {
      label: t("nav.users"),
      items: [
        { key: "pending", label: t("nav.pending"), icon: <HourglassMedium {...ICON_PROPS} /> },
        { key: "whitelist", label: t("nav.whitelist"), icon: <CheckCircle {...ICON_PROPS} /> },
        { key: "users", label: t("nav.allUsers"), icon: <Users {...ICON_PROPS} /> },
        { key: "roles", label: t("roles.tabLabel"), icon: <IdentificationCard {...ICON_PROPS} /> },
      ],
    },
    {
      label: t("nav.tools"),
      items: [
        { key: "tools", label: t("nav.toolsLabel"), icon: <Toolbox {...ICON_PROPS} /> },
        { key: "jobs", label: t("nav.allJobs"), icon: <Lightning {...ICON_PROPS} /> },
      ],
    },
    {
      label: t("nav.operations"),
      items: [
        { key: "stats", label: t("nav.jobStats"), icon: <ChartBar {...ICON_PROPS} /> },
        { key: "ki-stats", label: t("nav.kiStats"), icon: <ChartLineUp {...ICON_PROPS} /> },
      ],
    },
    {
      label: t("nav.playground"),
      items: [
        { key: "hilde", label: t("nav.hilde"), icon: <Bird {...ICON_PROPS} /> },
        { key: "francis", label: t("nav.francis"), icon: <Bird {...ICON_PROPS} /> },
      ],
    },
  ];

  const flatItems = (): NavItem[] => NAV.flatMap((g) => g.items);
  const findItem = (key: Tab): NavItem | undefined => flatItems().find((i) => i.key === key);

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
  const currentLabel = currentItem?.label ?? "";

  const selectTab = (k: Tab) => {
    setTab(k);
    setMobileNavOpen(false);
  };

  return (
    <div className="flex flex-col md:flex-row min-h-[calc(100vh-4rem)]">
      <div className="md:hidden flex items-center gap-3 px-4 h-12 border-b border-border-soft bg-background sticky top-0 z-20">
        <button
          onClick={() => setMobileNavOpen(true)}
          className="w-9 h-9 rounded-lg bg-surface border-2 border-transparent flex items-center justify-center text-muted transition-colors hover:border-kb hover:text-kb"
          aria-label={t("menuOpen")}
        >
          <List size={18} weight="bold" />
        </button>
        <div className="text-sm font-medium text-foreground-soft truncate">{currentLabel}</div>
      </div>

      {mobileNavOpen && (
        <button
          onClick={() => setMobileNavOpen(false)}
          aria-label={t("menuClose")}
          className="md:hidden fixed inset-0 top-16 bg-black/40 z-30"
        />
      )}

      <aside
        className={`bg-surface border-r border-border-soft p-3 flex flex-col gap-0.5 overflow-y-auto
          fixed md:sticky top-16 md:top-0 left-0 bottom-0 md:bottom-auto
          h-[calc(100vh-4rem)] md:h-screen
          w-72 md:w-60 z-40
          shadow-xl md:shadow-none
          transition-transform duration-200
          ${mobileNavOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
      >
        <div className="md:hidden flex items-center justify-between px-2 pt-1 pb-2">
          <span className="text-sm font-semibold">{t("title")}</span>
          <button
            onClick={() => setMobileNavOpen(false)}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-muted transition-colors hover:bg-surface-dim hover:text-kb"
            aria-label={t("close")}
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
                        ? "admin-nav-active text-kb dark:text-white font-semibold"
                        : "text-foreground-soft hover:bg-surface-dim hover:text-kb dark:hover:text-white"
                    }`}
                  >
                    <span
                      className={`transition-colors ${
                        active ? "text-kb dark:text-white" : "text-muted group-hover:text-kb dark:group-hover:text-white"
                      }`}
                    >
                      {item.icon}
                    </span>
                    <span className="flex-1">{item.label}</span>
                  </button>
                </div>
              );
            })}
          </div>
        ))}
      </aside>

      <main className="flex-1 min-w-0 px-4 py-6 md:px-8 md:py-8 lg:px-10">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-lg font-semibold mb-6">{currentLabel}</h2>

          {tab === "system" && <SettingsTab section="system" />}
          {tab === "ki" && <ProvidersTab />}
          {tab === "prompts" && <PromptsTab />}
          {tab === "diagnosis" && (
            <div className="flex flex-col gap-6">
              <div>
                <label className="text-sm font-medium text-foreground">
                  {t("diagnosisLanguage.label")}
                  <span className="ml-2 text-xs font-mono font-normal text-muted-soft">{"{language}"}</span>
                </label>
                <select
                  value="de"
                  disabled
                  aria-label={t("diagnosisLanguage.label")}
                  className="mt-1 block w-56 rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value="de">{t("diagnosisLanguage.german")}</option>
                </select>
                <p className="text-xs text-muted mt-1">{t("diagnosisLanguage.hint")}</p>
              </div>
              <DiagnosisQuestionPlanCard />
              <LanguageDiagnosisCard />
              <DiagnosisGradingCard />
              <DiagnosisExamplesCard />
              <DiagnosisAdaptiveBehaviorCard />
            </div>
          )}
          {tab === "pending" && <PendingTab />}
          {tab === "whitelist" && <WhitelistTab adminEmail={adminEmail} />}
          {tab === "users" && <UsersTab onOpenQuota={openQuotaForUser} />}
          {tab === "roles" && <RolesTab />}
          {tab === "tools" && <ToolsTab />}
          {tab === "jobs" && <JobsTab />}
          {tab === "stats" && <StatsTab />}
          {tab === "ki-stats" && <KiTutorTab />}
          {tab === "hilde" && <HildeTab />}
          {tab === "francis" && <FrancisTab />}
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
