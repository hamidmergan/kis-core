import { useEffect, useRef, useState } from "react";
import { DotsThreeVertical, SidebarSimple, Trash } from "@phosphor-icons/react";


interface ChatHeaderProps {
  messageCount: number;
  onClear: () => void;
  onMinimize?: () => void;
}


export function ChatHeader({ messageCount, onClear, onMinimize }: ChatHeaderProps) {
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const chatMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chatMenuOpen) return;
    function handle(e: MouseEvent) {
      if (!chatMenuRef.current?.contains(e.target as Node)) setChatMenuOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [chatMenuOpen]);

  return (
    <div className="flex items-center justify-between px-4 py-3 flex-shrink-0 relative" style={{ borderBottom: "1px solid var(--border)" }}>
      <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>Chat</span>
      <div className="flex items-center gap-1.5">
        <div className="relative" ref={chatMenuRef}>
          <button
            type="button"
            onClick={() => setChatMenuOpen((v) => !v)}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
            title="Optionen"
          >
            <DotsThreeVertical size={16} weight="bold" />
          </button>
          {chatMenuOpen && (
            <div
              className="absolute right-0 top-8 z-50 rounded-xl py-1"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", minWidth: 220, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}
            >
              <button
                type="button"
                onClick={() => { onClear(); setChatMenuOpen(false); }}
                disabled={messageCount === 0}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 disabled:opacity-40 transition-colors"
                style={{ color: "#B91C1C" }}
              >
                <Trash size={16} />
                Chatprotokoll löschen
              </button>
            </div>
          )}
        </div>
        {onMinimize && (
          <button
            type="button"
            onClick={onMinimize}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
            title="Panel minimieren"
          >
            <SidebarSimple size={13} />
          </button>
        )}
      </div>
    </div>
  );
}
