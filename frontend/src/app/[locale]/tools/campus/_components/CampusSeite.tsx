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

/** History on the left, the chat in the middle, the history as a drawer on the phone. */
export default function CampusSeite() {
  const t = useTranslations("tools.campus");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [config, setConfig] = useState<CampusConfig | null>(null);
  const verlauf = useChatVerlauf();

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

  const sidebar = (
    <ChatVerlauf
      chats={verlauf.chats}
      activeId={activeId}
      retentionDays={config?.retention_days ?? 0}
      onSelect={waehlen}
      onNew={neuerChat}
      onRename={verlauf.rename}
      onDelete={loeschen}
    />
  );

  return (
    <div className="viewport-shell flex flex-col overflow-hidden" style={{ backgroundColor: "var(--background)" }}>
      <CampusTopbar title={t("title")} menuOpen={menuOpen} onToggleMenu={() => setMenuOpen((v) => !v)} />
      <div className="flex flex-1 min-h-0 relative">
        <aside className="hidden md:flex flex-col w-72 flex-shrink-0 min-h-0" style={{ borderRight: "1px solid var(--border-soft)", backgroundColor: "var(--surface)" }}>
          {sidebar}
        </aside>
        {menuOpen && (
          <div className="md:hidden absolute inset-0 z-30 flex">
            <div className="w-72 max-w-[85%] h-full flex flex-col" style={{ backgroundColor: "var(--surface)", borderRight: "1px solid var(--border-soft)" }}>
              {sidebar}
            </div>
            <button type="button" aria-label={t("closeMenu")} onClick={() => setMenuOpen(false)} className="flex-1" style={{ backgroundColor: "rgba(0,0,0,0.35)" }} />
          </div>
        )}
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
