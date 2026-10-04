"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowDown } from "@phosphor-icons/react";
import { Signpost } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { ChatInputBar } from "@/app/[locale]/workspace/[uuid]/_components/chat/ChatInputBar";
import CampusNachricht from "./CampusNachricht";
import type { CampusConfig, CampusNachricht as Nachricht } from "../_types";

const BEISPIELE = ["example1", "example2", "example3", "example4"] as const;

export default function CampusChat({
  messages,
  loading,
  chatFull,
  config,
  onSend,
  onStop,
  onNewChat,
}: {
  messages: Nachricht[];
  loading: boolean;
  chatFull: boolean;
  config: CampusConfig | null;
  onSend: (text: string) => void;
  onStop: () => void;
  onNewChat: () => void;
}) {
  const t = useTranslations("tools.campus");
  const listRef = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(true);

  // Follows the answer while the reader stays at the bottom, otherwise a button offers the way down.
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (stuck) el.scrollTop = el.scrollHeight;
  }, [messages, stuck]);

  const onScroll = () => {
    const el = listRef.current;
    if (!el) return;
    setStuck(el.scrollHeight - el.scrollTop - el.clientHeight < 48);
  };

  const empty = messages.length === 0;
  const inputDisabled = chatFull;

  return (
    <div className="flex flex-col flex-1 min-h-0 relative">
      <div ref={listRef} onScroll={onScroll} className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-4" data-testid="campus-messages">
        <div className="mx-auto w-full flex flex-col gap-4" style={{ maxWidth: 920 }}>
          {empty ? (
            <div className="flex flex-col items-center text-center pt-10 pb-6 gap-4">
              <span className="flex items-center justify-center w-20 h-20 rounded-full bg-kb text-on-accent">
                <Signpost size={40} weight="bold" aria-hidden="true" />
              </span>
              <div>
                <h2 className="text-lg font-semibold" style={{ color: "var(--kb)" }}>{t("emptyTitle")}</h2>
                <p className="text-sm mt-1 max-w-md" style={{ color: "var(--muted)" }}>{t("emptyText")}</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl" data-testid="campus-examples">
                {BEISPIELE.map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => onSend(t(key))}
                    className="text-left text-sm px-4 py-3 rounded-xl border-2 border-border hover:border-kb focus:border-kb transition-colors bg-background"
                    style={{ color: "var(--foreground)" }}
                  >
                    {t(key)}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => <CampusNachricht key={m.id ?? `m-${i}`} msg={m} mapUrl={config?.map_url ?? ""} />)
          )}
          {chatFull && (
            <div className="flex items-center justify-between gap-3 flex-wrap px-4 py-3 rounded-xl text-sm" style={{ backgroundColor: "rgba(var(--kb-rgb),0.07)", color: "var(--foreground)" }}>
              <span>{t("chatFull")}</span>
              <button type="button" onClick={onNewChat} className="px-3 py-1.5 text-sm btn-primary rounded-md transition-colors">{t("newChat")}</button>
            </div>
          )}
        </div>
      </div>
      {!stuck && !empty && (
        <div className="absolute left-1/2 -translate-x-1/2" style={{ bottom: 104 }}>
          <IconButton size="lg" onClick={() => { setStuck(true); const el = listRef.current; if (el) el.scrollTop = el.scrollHeight; }} title={t("scrollToBottom")}>
            <ArrowDown size={16} weight="bold" />
          </IconButton>
        </div>
      )}
      <ChatInputBar
        loading={loading}
        onSend={onSend}
        onStop={onStop}
        placeholder={t("inputPlaceholder")}
        disabled={inputDisabled}
        maxLength={config?.max_question_chars ?? 2000}
      />
      <p className="text-center text-2xs px-6 pt-1.5 pb-2 hide-on-short" style={{ color: "var(--muted)" }}>{t("disclaimer")}</p>
    </div>
  );
}
