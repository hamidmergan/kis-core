"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Tabs from "@/components/ui/Tabs";
import ActiveToggle from "@/app/[locale]/workspace/_components/ActiveToggle";
import { copyTextFromPromise } from "@/lib/clipboard";

/** The share switch of a page, the module list's switch with the words of Pages. */
export function ShareSwitch({ on, isPublic, disabled, onToggle }: {
  on: boolean; isPublic?: boolean; disabled?: boolean; onToggle: (on: boolean) => void;
}) {
  const t = useTranslations("tools.pages");
  return (
    <ActiveToggle
      active={on}
      disabled={disabled}
      onToggle={onToggle}
      labels={{ on: isPublic ? t("sharedPublic") : t("shared"), off: t("private"), turnOn: t("shareOn"), turnOff: t("shareOff") }}
    />
  );
}

/** A small round copy button, it shows a tick for a moment after copying. */
export function CopyButton({ text, label }: { text: () => string; label: string }) {
  const t = useTranslations("tools.pages");
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        copyTextFromPromise(Promise.resolve(text()));
        setDone(true);
        window.setTimeout(() => setDone(false), 1400);
      }}
      className="w-7 h-7 flex items-center justify-center rounded-full btn-icon flex-shrink-0"
      style={{ backgroundColor: "var(--surface-dim)" }}
      title={done ? t("copied") : label}
      aria-label={label}
    >
      {done ? <Check size={13} weight="bold" /> : <Copy size={13} weight="bold" />}
    </button>
  );
}

interface ShareModalProps {
  open: boolean;
  onClose: () => void;
  shared: boolean;
  isPublic: boolean;
  link: string | null;
  busy: boolean;
  onToggle: (on: boolean) => void;
  onAudience: (isPublic: boolean) => void;
}

/** Sharing one page: the switch, who the link opens for, and the link once it is on. */
export function ShareModal({ open, onClose, shared, isPublic, link, busy, onToggle, onAudience }: ShareModalProps) {
  const t = useTranslations("tools.pages");
  const [copied, setCopied] = useState(false);
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title={t("shareModalTitle")}
      footer={<button type="button" className="px-4 py-2 text-sm btn-primary rounded-lg" onClick={onClose}>{t("done")}</button>}
    >
      <ShareSwitch on={shared} isPublic={isPublic} disabled={busy} onToggle={onToggle} />
      {shared && (
        <Tabs<"intern" | "extern">
          variant="pill"
          className="mt-4"
          active={isPublic ? "extern" : "intern"}
          onChange={(k) => { if (!busy) onAudience(k === "extern"); }}
          items={[{ key: "intern", label: t("audienceInternal") }, { key: "extern", label: t("audiencePublic") }]}
        />
      )}
      <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>{shared && isPublic ? t("sharePublicNote") : t("shareNote")}</p>
      {shared && link && (
        <>
          <div className="flex gap-2 mt-4">
            <input
              readOnly
              value={link}
              aria-label={t("linkAria")}
              onFocus={(e) => e.currentTarget.select()}
              className="flex-1 min-w-0 px-3 py-1.5 text-sm rounded-md border-2 border-border-soft bg-surface"
            />
            <button
              type="button"
              className="px-3.5 py-1.5 text-sm font-medium btn-secondary rounded-lg whitespace-nowrap"
              onClick={() => {
                copyTextFromPromise(Promise.resolve(link));
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1400);
              }}
            >
              {copied ? t("copied") : t("copyLink")}
            </button>
          </div>
          <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>{t("shareOffNote")}</p>
          <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{t("workspaceNote")}</p>
        </>
      )}
    </Modal>
  );
}
