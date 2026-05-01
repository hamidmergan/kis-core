"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Globe, List, Moon, Sidebar, SignOut, Stack, Sun, UserCircleGear, X } from "@phosphor-icons/react";

interface HeaderMobileMenuProps {
  isAdmin: boolean;
  showToolsToggle?: boolean;
  onLogout: () => void;
}

type Lang = "de" | "en";
type Theme = "light" | "dark";

export default function HeaderMobileMenu({ isAdmin, showToolsToggle = false, onLogout }: HeaderMobileMenuProps) {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<Lang>("de");
  const [theme, setTheme] = useState<Theme>("light");
  const ref = useRef<HTMLDivElement>(null);
  const isDark = theme === "dark";

  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);

  const rowClass =
    "flex items-center gap-3 w-full px-4 py-2.5 text-sm font-medium hover:bg-[var(--surface-dim)] transition-colors no-underline text-left";

  return (
    <div className="sm:hidden relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Menü schließen" : "Menü öffnen"}
        aria-expanded={open}
        className="flex items-center justify-center w-10 h-10 rounded-full btn-on-dark"
      >
        {open ? <X size={20} weight="bold" /> : <List size={20} weight="bold" />}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 z-50 w-56 rounded-xl py-1 overflow-hidden"
          style={{
            backgroundColor: "var(--surface)",
            border: "1px solid var(--border)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
          }}
        >
          <button
            type="button"
            onClick={() => setLang(lang === "de" ? "en" : "de")}
            className={rowClass}
            style={{ color: "var(--foreground)" }}
            aria-label="Sprache wechseln"
          >
            <Globe size={20} weight="bold" />
            <span className="flex-1">Sprache</span>
            <span className="text-xs font-mono uppercase" style={{ color: "var(--muted)" }}>{lang}</span>
          </button>
          <button
            type="button"
            onClick={() => setTheme(isDark ? "light" : "dark")}
            className={rowClass}
            style={{ color: "var(--foreground)", borderBottom: "1px solid var(--border)" }}
            aria-label={isDark ? "Heller Modus" : "Dunkler Modus"}
          >
            {isDark ? <Moon size={20} weight="bold" /> : <Sun size={20} weight="bold" />}
            <span className="flex-1">{isDark ? "Dunkel" : "Hell"}</span>
          </button>
          {showToolsToggle && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                window.dispatchEvent(new Event("tools-sidebar:open"));
              }}
              className={rowClass}
              style={{ color: "var(--foreground)" }}
            >
              <Sidebar size={20} weight="bold" />
              <span>Tools</span>
            </button>
          )}
          <Link
            href="/my-jobs"
            onClick={() => setOpen(false)}
            className={rowClass}
            style={{ color: "var(--foreground)" }}
          >
            <Stack size={20} weight="bold" />
            <span>Jobs</span>
          </Link>
          {isAdmin && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className={rowClass}
              style={{ color: "var(--foreground)" }}
            >
              <UserCircleGear size={20} weight="bold" />
              <span>Admin</span>
            </Link>
          )}
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className={rowClass}
            style={{ color: "var(--foreground)", borderTop: "1px solid var(--border)" }}
          >
            <SignOut size={20} weight="bold" />
            <span>Abmelden</span>
          </button>
        </div>
      )}
    </div>
  );
}
