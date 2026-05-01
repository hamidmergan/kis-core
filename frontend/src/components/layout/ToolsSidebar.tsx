"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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

type SidebarTool = { key: string; title: string; href: string; icon: Icon };

const TOOLS: SidebarTool[] = [
  { key: "translation",   title: "Übersetzung",     href: "/tools/translate",  icon: Translate },
  { key: "tts",           title: "Text in Sprache", href: "/tools/tts",        icon: SpeakerHigh },
  { key: "transcription", title: "Sprache in Text", href: "/tools/stt",        icon: Microphone },
  { key: "image",         title: "Bildgenerierung", href: "/tools/image",      icon: ImageIcon },
  { key: "summary",       title: "Zusammenfassung", href: "/tools/summarize",  icon: TextAlignLeft },
  { key: "screencast",    title: "Screencast",      href: "/tools/screencast", icon: MonitorPlay },
  { key: "glossary",      title: "Glossar",         href: "/tools/glossary",   icon: BookOpen },
];

const STORAGE_KEY = "kis_tools_sidebar_collapsed";

export default function ToolsSidebar() {
  const { loaded, isToolEnabled } = useEnabledTools();
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

  if (!loaded || !hydrated) return null;

  const tools = TOOLS.filter((t) => isToolEnabled(t.key));
  if (tools.length === 0) return null;

  const effectiveCollapsed = userPref !== null ? userPref : !isLarge;

  if (isSmartphone && effectiveCollapsed) return null;

  function toggle() {
    const next = !effectiveCollapsed;
    setUserPref(next);
    try { localStorage.setItem(STORAGE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
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
              Tools
            </h2>
          )}
          <button
            type="button"
            onClick={toggle}
            aria-label={effectiveCollapsed ? "Tools-Sidebar ausklappen" : "Tools-Sidebar einklappen"}
            className="flex items-center justify-center rounded-md w-7 h-7 transition-colors hover:bg-[var(--surface-dim)]"
            style={{ color: "var(--kb)" }}
          >
            <Sidebar size={18} weight="bold" />
          </button>
        </div>

        <ul className="flex flex-col gap-1">
          {tools.map((tool) => {
            const ToolIcon = tool.icon;
            return (
              <li key={tool.key}>
                <Link
                  href={tool.href}
                  title={effectiveCollapsed ? tool.title : undefined}
                  className={`tools-sidebar-item flex items-center gap-3 rounded-lg no-underline transition-colors hover:bg-surface-dim ${effectiveCollapsed ? "justify-center px-1 py-2" : "px-2 py-2"}`}
                >
                  <span className="tools-sidebar-item__box flex items-center justify-center flex-shrink-0 w-10 h-10 rounded-lg">
                    <ToolIcon size={18} weight="bold" />
                  </span>
                  {!effectiveCollapsed && (
                    <span
                      className="text-[15px] truncate"
                      style={{ color: "var(--foreground)" }}
                    >
                      {tool.title}
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
