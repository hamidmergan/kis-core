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
  { key: "glossary",      title: "Glossar",         href: "/tools/glossary",   icon: BookOpen },
  { key: "screencast",    title: "Screencast",      href: "/tools/screencast", icon: MonitorPlay },
];

const STORAGE_KEY = "kis_tools_sidebar_collapsed";

export default function ToolsSidebar() {
  const { loaded, isToolEnabled } = useEnabledTools();
  const [userPref, setUserPref] = useState<boolean | null>(null);
  const [isLarge, setIsLarge] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "1") setUserPref(true);
      else if (stored === "0") setUserPref(false);
    } catch { /* ignore */ }

    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setIsLarge(mq.matches);
    update();
    mq.addEventListener("change", update);

    setHydrated(true);
    return () => mq.removeEventListener("change", update);
  }, []);

  if (!loaded || !hydrated) return null;

  const tools = TOOLS.filter((t) => isToolEnabled(t.key));
  if (tools.length === 0) return null;

  const effectiveCollapsed = userPref !== null ? userPref : !isLarge;

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
          className={`mb-4 ${effectiveCollapsed ? "flex flex-col items-center gap-1" : "flex items-center"}`}
          style={{ minHeight: 28 }}
        >
          {!effectiveCollapsed && (
            <span
              className="text-[11px] font-bold uppercase tracking-wider flex-1 px-1"
              style={{ color: "var(--muted)" }}
            >
              Tools
            </span>
          )}
          <button
            type="button"
            onClick={toggle}
            aria-label={effectiveCollapsed ? "Tools-Sidebar ausklappen" : "Tools-Sidebar einklappen"}
            className="flex items-center justify-center rounded-md w-7 h-7 hover:bg-[var(--bg)] transition-colors"
            style={{ color: "var(--kb)" }}
          >
            <Sidebar size={18} weight="bold" />
          </button>
          {effectiveCollapsed && (
            <span
              className="text-[10px] font-bold uppercase tracking-wider mt-3"
              style={{ color: "var(--muted)" }}
            >
              Tools
            </span>
          )}
        </div>

        <ul className="flex flex-col gap-1">
          {tools.map((tool) => {
            const ToolIcon = tool.icon;
            return (
              <li key={tool.key}>
                <Link
                  href={tool.href}
                  title={effectiveCollapsed ? tool.title : undefined}
                  className={`flex items-center gap-3 rounded-lg no-underline transition-colors hover:bg-[var(--bg)] ${effectiveCollapsed ? "justify-center px-1 py-2" : "px-2 py-2"}`}
                >
                  <span
                    className="flex items-center justify-center flex-shrink-0 w-10 h-10 rounded-lg"
                    style={{
                      backgroundColor: "var(--bg)",
                      border: "1px solid var(--border)",
                      color: "var(--kb)",
                    }}
                  >
                    <ToolIcon size={22} weight="bold" />
                  </span>
                  {!effectiveCollapsed && (
                    <span
                      className="text-[15px] font-medium truncate"
                      style={{ color: "var(--text)" }}
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
