import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { DotsThreeVertical, SidebarSimple, Trash } from "@phosphor-icons/react";


interface ChatHeaderProps {
  messageCount: number;
  onClear: () => void;
  onMinimize?: () => void;
  /** Mobile: only the buttons in a narrow row, the tab bar carries the title. */
  compact?: boolean;
}


export function ChatHeader({ messageCount, onClear, onMinimize, compact = false }: ChatHeaderProps) {
  const t = useTranslations("workspace.detail.chat");
  const tPanels = useTranslations("workspace.detail.panels");
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
    <div
      data-panel-header=""
      className={`flex items-center flex-shrink-0 relative ${compact ? "justify-end px-3 py-1.5" : "justify-between px-4 py-3"}`}
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      {!compact && (
        <span className="text-base font-semibold" style={{ color: "var(--foreground)" }}>{t("title")}</span>
      )}
      <div className="flex items-center gap-1.5">
        <div className="relative" ref={chatMenuRef}>
          <button
            type="button"
            onClick={() => setChatMenuOpen((v) => !v)}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title={t("options")}
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
                className="w-full flex items-center gap-2 px-4 py-2.5 text-base text-left hover:bg-[var(--surface-dim)] disabled:opacity-40 transition-colors"
                style={{ color: "rgb(185, 28, 28)" }}
              >
                <Trash size={16} />
                {t("clearLog")}
              </button>
            </div>
          )}
        </div>
        {onMinimize && !compact && (
          <button
            type="button"
            onClick={onMinimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title={tPanels("minimize")}
          >
            <SidebarSimple size={13} />
          </button>
        )}
      </div>
    </div>
  );
}
