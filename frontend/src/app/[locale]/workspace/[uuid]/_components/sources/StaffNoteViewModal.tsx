"use client";

import { useTranslations } from "next-intl";
import { Globe } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import type { StaffNoteLink } from "../../_types";

interface StaffNoteViewModalProps {
  open: boolean;
  text: string | null | undefined;
  links: StaffNoteLink[];
  onClose: () => void;
}

/** The note as readers see it, opened from the pin in the panel header. */
export function StaffNoteViewModal({ open, text, links, onClose }: StaffNoteViewModalProps) {
  const t = useTranslations("workspace.detail.sources.staffNote");
  return (
    <Modal open={open} onClose={onClose} title={t("title")}>
      <div className="space-y-3">
        {text && text.trim() && (
          <p
            className="text-sm leading-relaxed whitespace-pre-wrap break-words"
            style={{ color: "var(--foreground)" }}
          >
            {text}
          </p>
        )}
        {links.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {links.map((link, i) => (
              <li key={`${link.url}-${i}`}>
                <LinkChip url={link.url} label={link.label} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}

function LinkChip({ url, label }: { url: string; label: string }) {
  const domain = extractDomain(url);
  const istMail = url.toLowerCase().startsWith("mailto:");
  return (
    <a
      href={url}
      /** A mailto: in a new tab leaves an empty error tab behind. */
      target={istMail ? undefined : "_blank"}
      rel={istMail ? undefined : "noopener noreferrer"}
      className="group flex items-center gap-2 rounded-md px-2.5 py-1.5 transition-colors"
      style={{
        backgroundColor: "rgba(var(--kb-rgb), 0.08)",
        border: "1px solid rgba(var(--kb-rgb), 0.16)",
        color: "var(--foreground)",
      }}
      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb), 0.16)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb), 0.08)"; }}
    >
      <Globe size={14} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
      <span className="text-sm font-medium truncate flex-1 min-w-0">{label}</span>
      <span className="text-xs truncate flex-shrink-0" style={{ color: "var(--muted)" }}>
        {domain}
      </span>
    </a>
  );
}

function extractDomain(url: string): string {
  try {
    if (url.toLowerCase().startsWith("mailto:")) return url.slice(7);
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
