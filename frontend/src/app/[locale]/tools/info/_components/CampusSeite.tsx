"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi } from "@/lib/api";
import CampusTopbar from "./CampusTopbar";
import ChatVerlauf from "./ChatVerlauf";
import CampusChat from "./CampusChat";
import { useCampusChat } from "../_hooks/useCampusChat";
import { useChatVerlauf } from "../_hooks/useChatVerlauf";
import type { CampusConfig } from "../_types";

const COLLAPSED_KEY = "campus.sidebarCollapsed";

/** History on the left, the chat in the middle, the history as a drawer on the phone. */
export default function CampusSeite() {
  const t = useTranslations("tools.campus");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [config, setConfig] = useState<CampusConfig | null>(null);
  const verlauf = useChatVerlauf();

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "1");
    } catch {
      // Without storage the bar simply starts open.
    }
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((v) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, v ? "0" : "1");
      } catch {
        // The choice then only lasts for this visit.
      }
      return !v;
    });
  };

  useEffect(() => {
    backendApi.getJson<CampusConfig>("/campus/config").then(setConfig).catch(() => setConfig(null));
  }, []);

  const onChatCreated = useCallback(
    (chatId: number, title: string) => {
      setActiveId(chatId);
      const now = new Date().toISOString().replace("Z", "");
      verlauf.upsertTop({ id: chatId, title, question_count: 1, created_at: now, updated_at: now });
    },
    [verlauf],
  );
  const onAnswered = useCallback(() => {
    verlauf.reload();
  }, [verlauf]);

  const chat = useCampusChat({ chatId: activeId, onChatCreated, onAnswered });

  const neuerChat = () => {
    setActiveId(null);
    setMenuOpen(false);
  };
  const waehlen = (id: number) => {
    setActiveId(id);
    setMenuOpen(false);
  };
  const loeschen = async (id: number) => {
    await verlauf.remove(id);
    if (id === activeId) setActiveId(null);
  };

  const sidebar = (collapsedView: boolean, onToggle: () => void) => (
    <ChatVerlauf
      chats={verlauf.chats}
      activeId={activeId}
      retentionDays={config?.retention_days ?? 0}
      onSelect={waehlen}
      onNew={neuerChat}
      onRename={verlauf.rename}
      onDelete={loeschen}
      collapsed={collapsedView}
      onToggle={onToggle}
    />
  );

  return (
    <div className="viewport-shell flex overflow-hidden" style={{ backgroundColor: "var(--background)" }}>
      <aside
        className={`hidden md:flex flex-col flex-shrink-0 min-h-0 transition-[width] duration-200 ${collapsed ? "w-14" : "w-72"}`}
        style={{ borderRight: "1px solid var(--border-soft)", backgroundColor: "var(--surface)" }}
      >
        {sidebar(collapsed, toggleCollapsed)}
      </aside>
      {menuOpen && (
        <div className="md:hidden fixed inset-0 z-30 flex">
          <div className="w-[82%] max-w-sm h-full flex flex-col" style={{ backgroundColor: "var(--surface)", borderRight: "1px solid var(--border-soft)" }}>
            {sidebar(false, () => setMenuOpen(false))}
          </div>
          <button type="button" aria-label={t("closeMenu")} onClick={() => setMenuOpen(false)} className="flex-1" style={{ backgroundColor: "rgba(0,0,0,0.35)" }} />
        </div>
      )}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        <h1 className="sr-only">{t("title")}</h1>
        <CampusTopbar onOpenMenu={() => setMenuOpen(true)} />
        <main className="flex flex-col flex-1 min-w-0 min-h-0">
          <CampusChat
            messages={chat.messages}
            loading={chat.loading}
            chatFull={chat.chatFull}
            config={config}
            onSend={chat.send}
            onStop={chat.stop}
            onRate={chat.rate}
            onNewChat={neuerChat}
          />
        </main>
      </div>
    </div>
  );
}
