"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { List, Sidebar, SignOut, Stack, UserCircleGear, X } from "@phosphor-icons/react";

interface HeaderMobileMenuProps {
  isAdmin: boolean;
  showToolsToggle?: boolean;
  onLogout: () => void;
}

export default function HeaderMobileMenu({ isAdmin, showToolsToggle = false, onLogout }: HeaderMobileMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);

  const rowClass =
    "flex items-center gap-3 w-full px-4 py-3 text-[15px] font-medium hover:outline-2 hover:outline-primary -outline-offset-2 transition no-underline text-left";

  return (
    <div className="sm:hidden relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Menü schließen" : "Menü öffnen"}
        aria-expanded={open}
        className="flex items-center justify-center w-10 h-10 rounded-full text-white/80 hover:text-white hover:outline-2 hover:outline-white transition"
      >
        {open ? <X size={20} weight="bold" /> : <List size={20} weight="bold" />}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 z-50 w-56 rounded-xl shadow-xl overflow-hidden"
          style={{ backgroundColor: "var(--bg)", border: "1px solid var(--border)" }}
        >
          {showToolsToggle && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                window.dispatchEvent(new Event("tools-sidebar:open"));
              }}
              className={rowClass}
              style={{ color: "var(--text)" }}
            >
              <Sidebar size={20} weight="bold" />
              <span>Tools</span>
            </button>
          )}
          <Link
            href="/my-jobs"
            onClick={() => setOpen(false)}
            className={rowClass}
            style={{ color: "var(--text)" }}
          >
            <Stack size={20} weight="bold" />
            <span>Jobs</span>
          </Link>
          {isAdmin && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className={rowClass}
              style={{ color: "var(--text)" }}
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
            style={{ color: "var(--text)", borderTop: "1px solid var(--border)" }}
          >
            <SignOut size={20} weight="bold" />
            <span>Abmelden</span>
          </button>
        </div>
      )}
    </div>
  );
}
