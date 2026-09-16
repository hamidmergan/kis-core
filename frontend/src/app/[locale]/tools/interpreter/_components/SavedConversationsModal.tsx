"use client";

import { useTranslations } from "next-intl";
import { Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import Modal from "@/components/ui/Modal";
import type { SessionSummary } from "../_api";
import { MAX_SESSIONS, sessionsFull } from "../_limits";

interface Props {
  open: boolean;
  onClose: () => void;
  list: SessionSummary[];
  loading: boolean;
  currentId: string | null;
  onOpen: (entry: SessionSummary) => void;
  onDelete: (id: string) => void;
  formatDate: (iso: string) => string;
}

/** The first sentence names the conversation. */
function titleOf(entry: SessionSummary): string {
  const text = entry.first_original;
  return text.length > 80 ? `${text.slice(0, 77)}…` : text;
}

/** Every conversation that was started, to read again or to continue. */
export default function SavedConversationsModal({ open, onClose, list, loading, currentId, onOpen, onDelete, formatDate }: Props) {
  const t = useTranslations("tools.interpreter.saved");
  const full = sessionsFull(list.length);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("title")}
      size="md"
      footer={
        <button type="button" onClick={onClose} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
          {t("close")}
        </button>
      }
    >
      <p className="text-sm text-muted mb-1">{t("intro")}</p>
      <p className="text-sm text-muted mb-4">{t("rule", { max: MAX_SESSIONS })}</p>
      {full && (
        <p className="mb-4 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="alert">
          {t("full", { max: MAX_SESSIONS })}
        </p>
      )}
      {loading && list.length === 0 ? (
        <p className="text-sm text-muted-soft">…</p>
      ) : list.length === 0 ? (
        <p className="text-sm text-muted-soft">{t("empty")}</p>
      ) : (
        <ul className="space-y-2">
          {list.map((entry, index) => {
            const current = entry.id === currentId;
            const nextOut = full && index === list.length - 1;
            return (
              <li
                key={entry.id}
                className={`flex items-center gap-3 rounded-xl border-2 px-4 py-3 transition-colors ${current ? "border-kb" : "border-border-soft hover:border-kb"}`}
              >
                <button type="button" onClick={() => onOpen(entry)} className="flex-1 min-w-0 text-left">
                  <p className="text-sm text-foreground truncate">{titleOf(entry) || t("untitled")}</p>
                  <p className="flex flex-wrap gap-x-3 text-xs text-muted-soft">
                    <span>{formatDate(entry.updated_at)}</span>
                    <span>{t("sentences", { count: entry.turn_count })}</span>
                    {entry.ended && <span>{t("ended")}</span>}
                    {current && <span>{t("current")}</span>}
                    {nextOut && <span className="text-warn-strong">{t("nextOut")}</span>}
                  </p>
                </button>
                <IconButton size="sm" onClick={() => onDelete(entry.id)} aria-label={t("delete")} title={t("delete")}>
                  <Trash size={12} weight="bold" />
                </IconButton>
              </li>
            );
          })}
        </ul>
      )}
    </Modal>
  );
}
