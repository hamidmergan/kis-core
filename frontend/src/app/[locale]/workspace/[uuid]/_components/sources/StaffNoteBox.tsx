"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretDown, PushPin, Globe } from "@phosphor-icons/react";
import type { StaffNoteLink } from "../../_types";

interface StaffNoteBoxProps {
  text: string | null | undefined;
  links: StaffNoteLink[];
  workspaceUuid: string;
}

const STORAGE_KEY_PREFIX = "kis-staff-note-open-";

export function StaffNoteBox({ text, links, workspaceUuid }: StaffNoteBoxProps) {
  const t = useTranslations("workspace.detail.sources.staffNote");
  const storageKey = STORAGE_KEY_PREFIX + workspaceUuid;
  const hasContent = Boolean((text && text.trim()) || (links && links.length > 0));

  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved === "1") setOpen(true);
    } catch { /* ignore */ }
  }, [storageKey]);

  useEffect(() => {
    try { localStorage.setItem(storageKey, open ? "1" : "0"); } catch { /* ignore */ }
  }, [storageKey, open]);

  // Ohne Inhalt keine Box, angelegt wird der Hinweis ueber den Knopf in der Kopfzeile.
  if (!hasContent) return null;

  return (
    <div
      className="px-4 py-2 flex-shrink-0"
      style={{ borderBottom: "1px solid var(--border)" }}
      // Der Rundgang zeigt Studierenden den Kasten, denn die Pinnnadel fehlt ihnen.
      data-tour="staff-note"
    >
      <div
        className="rounded-lg overflow-hidden"
        style={{
          backgroundColor: "var(--surface-dim)",
          borderLeft: "3px solid var(--accent)",
          border: "1px solid var(--border)",
          borderLeftWidth: 3,
        }}
      >
        <div className="flex items-center gap-2 px-3 py-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? t("collapse") : t("expand")}
            aria-expanded={open}
            className="flex-1 flex items-center gap-2 text-left text-sm font-medium"
            style={{ color: "var(--foreground)" }}
          >
            <PushPin size={14} weight="bold" style={{ color: "var(--accent)", flexShrink: 0 }} />
            <span className="truncate">{t("title")}</span>
          </button>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? t("collapse") : t("expand")}
            className="w-7 h-7 flex items-center justify-center text-[var(--muted)] hover:text-[var(--kb)] transition-colors"
          >
            <CaretDown
              size={13}
              weight="bold"
              style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 150ms" }}
            />
          </button>
        </div>

        {open && (
          <div
            className="px-3 pb-3 pt-1 space-y-3 overflow-y-auto overscroll-contain"
            style={{ borderTop: "1px solid var(--border)", maxHeight: "40vh" }}
          >
            {text && text.trim() && (
              <p
                className="text-sm leading-relaxed whitespace-pre-wrap break-words pt-2"
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
        )}
      </div>
    </div>
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
