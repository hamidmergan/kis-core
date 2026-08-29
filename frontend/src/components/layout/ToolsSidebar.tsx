"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { usePathname } from "@/i18n/navigation";
import {
  Sidebar,
  Translate,
  SpeakerHigh,
  Microphone,
  Image as ImageIcon,
  TextAlignLeft,
  BookOpen,
  MonitorPlay,
  type Icon,
} from "@phosphor-icons/react";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import { usePermissions } from "@/hooks/usePermissions";
import { TOOL_ROUTES, type ToolKey } from "@/lib/modules";

type SidebarItemKey = ToolKey;
type SidebarTool = { key: SidebarItemKey; href: string; icon: Icon };

const ICONS: Record<SidebarItemKey, Icon> = {
  translation: Translate,
  tts: SpeakerHigh,
  transcription: Microphone,
  image: ImageIcon,
  summary: TextAlignLeft,
  screencast: MonitorPlay,
  glossary: BookOpen,
};

const TOOLS: SidebarTool[] = TOOL_ROUTES.map((t) => ({
  key: t.key,
  href: t.href,
  icon: ICONS[t.key],
}));

const STORAGE_KEY = "kis_tools_sidebar_collapsed";

export default function ToolsSidebar() {
  const t = useTranslations("toolsSidebar");
  const pathname = usePathname();
  const { loaded, isToolEnabled } = useEnabledTools();
  const { loaded: permsLoaded, permissions } = usePermissions();
  const [userPref, setUserPref] = useState<boolean | null>(null);
  const [isLarge, setIsLarge] = useState(false);
  const [isSmartphone, setIsSmartphone] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "1") setUserPref(true);
      else if (stored === "0") setUserPref(false);
    } catch { /* ignore */ }

    const mqLarge = window.matchMedia("(min-width: 1024px)");
    const mqPhone = window.matchMedia("(max-width: 767px)");
    const updateLarge = () => setIsLarge(mqLarge.matches);
    const updatePhone = () => setIsSmartphone(mqPhone.matches);
    updateLarge();
    updatePhone();
    mqLarge.addEventListener("change", updateLarge);
    mqPhone.addEventListener("change", updatePhone);

    const openHandler = () => {
      setUserPref(false);
      try { localStorage.setItem(STORAGE_KEY, "0"); } catch { /* ignore */ }
    };
    window.addEventListener("tools-sidebar:open", openHandler);

    setHydrated(true);
    return () => {
      mqLarge.removeEventListener("change", updateLarge);
      mqPhone.removeEventListener("change", updatePhone);
      window.removeEventListener("tools-sidebar:open", openHandler);
    };
  }, []);

  if (!loaded || !permsLoaded || !hydrated) return null;

  const tools = TOOLS.filter((t) => isToolEnabled(t.key) && permissions.tools.includes(t.key));
  if (tools.length === 0) return null;

  const effectiveCollapsed = userPref !== null ? userPref : true;

  if (isSmartphone && effectiveCollapsed) return null;

  function toggle() {
    const next = !effectiveCollapsed;
    setUserPref(next);
    try { localStorage.setItem(STORAGE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
  }

  // Below 1024px the open sidebar covers the whole page, so it closes after picking a tool.
  function closeOnSmallScreen() {
    if (isLarge) return;
    setUserPref(true);
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch { /* ignore */ }
  }

  const expandedWidth = isLarge ? "w-[17.5rem]" : "w-full";

  return (
    <aside
      className={`flex-shrink-0 transition-[width] duration-200 self-stretch ${effectiveCollapsed ? "w-20" : expandedWidth}`}
      style={{
        backgroundColor: "var(--surface)",
        borderRight: "1px solid var(--border)",
      }}
    >
      <div className="sticky top-0 px-3 pt-6 pb-4">
        <div
          className={`mb-4 flex items-center ${effectiveCollapsed ? "justify-center" : "justify-between"}`}
          style={{ minHeight: 28 }}
        >
          {!effectiveCollapsed && (
            <h2
              className="text-base font-semibold tracking-tight px-2"
              style={{ color: "var(--kb)" }}
            >
              {t("heading")}
            </h2>
          )}
          <button
            type="button"
            onClick={toggle}
            aria-label={effectiveCollapsed ? t("expand") : t("collapse")}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          >
            <Sidebar size={18} weight="bold" />
          </button>
        </div>

        <ul className="flex flex-col gap-1">
          {tools.map((tool) => {
            const ToolIcon = tool.icon;
            const title = t(`items.${tool.key}`);
            const isActive = pathname === tool.href || pathname.startsWith(`${tool.href}/`);
            return (
              <li key={tool.key}>
                <Link
                  href={tool.href}
                  onClick={closeOnSmallScreen}
                  title={effectiveCollapsed ? title : undefined}
                  aria-current={isActive ? "page" : undefined}
                  className={`tools-sidebar-item flex items-center gap-3 rounded-lg no-underline transition-colors ${isActive ? "is-active" : ""} ${effectiveCollapsed ? "justify-center px-1 py-2" : "px-2 py-2"}`}
                >
                  <span className="tools-sidebar-item__box flex items-center justify-center flex-shrink-0 w-10 h-10 rounded-lg">
                    <ToolIcon size={18} weight="bold" />
                  </span>
                  {!effectiveCollapsed && (
                    <span
                      className="text-sm truncate"
                      style={{ color: "var(--foreground)" }}
                    >
                      {title}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
