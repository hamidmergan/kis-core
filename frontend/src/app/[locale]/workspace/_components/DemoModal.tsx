"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import type { DemoWorkspace } from "./useDemoWorkspaces";

interface Props {
  open: boolean;
  onClose: () => void;
  items: DemoWorkspace[];
  busy: string | null;
  onJoin: (uuid: string | null) => void;
  onLeave: (uuid: string) => void;
}

/** All demo courses in one dialog, join and leave again. */
export default function DemoModal({ open, onClose, items, busy, onJoin, onLeave }: Props) {
  const t = useTranslations("workspace.demo");
  const offene = items.filter((m) => !m.joined).length;

  const fuss = (
    <div className="flex items-center gap-3 w-full">
      {offene > 0 && (
        <button
          type="button"
          data-testid="demo-join-all"
          onClick={() => onJoin(null)}
          disabled={busy !== null}
          className="btn-primary ml-auto text-sm rounded-lg px-4 py-2 disabled:opacity-50"
        >
          {busy === "all" ? "…" : t("joinAll")}
        </button>
      )}
    </div>
  );

  return (
    <Modal open={open} onClose={onClose} title={t("title")} size="lg" footer={fuss}>
      <p className="text-xs text-muted mb-4">{t("subtitle")}</p>

      <div className="flex flex-col gap-2" data-testid="demo-list">
        {items.map((m) => (
          <div
            key={m.uuid}
            className="flex items-center gap-4 rounded-lg border border-border-soft bg-background px-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{m.title}</p>
              {m.description && <p className="text-xs text-muted truncate">{m.description}</p>}
            </div>
            <span className="ml-auto text-xs text-muted-soft whitespace-nowrap">
              {t("sources", { n: m.source_count })}
            </span>
            {/* Wer ueber einen richtigen Link drin sitzt, hat hier nichts zu tun. */}
            {m.joined && !m.via_demo && (
              <span className="text-xs text-muted-soft whitespace-nowrap">{t("alreadyIn")}</span>
            )}
            {(!m.joined || m.via_demo) && (
              <button
                type="button"
                data-testid={m.joined ? "demo-leave" : "demo-join"}
                onClick={() => (m.joined ? onLeave(m.uuid) : onJoin(m.uuid))}
                disabled={busy !== null}
                className="btn-secondary text-sm rounded-lg px-3 py-1.5 disabled:opacity-50 whitespace-nowrap"
              >
                {busy === m.uuid ? "…" : m.joined ? t("leave") : t("join")}
              </button>
            )}
          </div>
        ))}
      </div>
    </Modal>
  );
}
