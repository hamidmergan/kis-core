"use client";

import { Sidebar } from "@phosphor-icons/react";

export default function MobileSidebarToggle() {
  return (
    <div className="md:hidden mb-4">
      <button
        type="button"
        onClick={() => window.dispatchEvent(new Event("tools-sidebar:open"))}
        aria-label="Tools-Sidebar öffnen"
        className="flex items-center justify-center rounded-md w-9 h-9 transition-colors hover:bg-[var(--bg)]"
        style={{
          backgroundColor: "var(--surface)",
          border: "1px solid var(--border)",
          color: "var(--kb)",
        }}
      >
        <Sidebar size={18} weight="bold" />
      </button>
    </div>
  );
}
