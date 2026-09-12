"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CalendarBlank, Check, Copy, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { copyTextFromPromise } from "@/lib/clipboard";
import type { AccessLink } from "../_shared";

interface LinkRowProps {
  link: AccessLink;
  onRequestDelete: (link: AccessLink) => void;
}

export default function LinkRow({ link, onRequestDelete }: LinkRowProps) {
  const t = useTranslations("workspace.list");
  const locale = useLocale();
  const [copied, setCopied] = useState<"link" | "code" | null>(null);
  const enrollLink = `${typeof window !== "undefined" ? window.location.origin : ""}/workspace?code=${link.code}`;
  const expiresDate = link.expires_at
    ? new Date(link.expires_at).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Berlin",
      })
    : null;
  const isExpired = link.expires_at ? new Date(link.expires_at) < new Date() : false;

  function handleCopy(was: "link" | "code") {
    copyTextFromPromise(Promise.resolve(was === "link" ? enrollLink : link.code));
    setCopied(was);
    setTimeout(() => setCopied(null), 2000);
  }

  const chipClass = isExpired
    ? "border-error-border bg-error-bg hover:bg-error-bg"
    : "border-border-soft bg-surface hover:bg-surface hover:border-border";

  return (
    <div className="group/row flex items-center gap-2 min-w-0 -mx-2 px-2 py-1 rounded-lg hover:bg-surface-dim/50 transition-colors">
      <button
        onClick={() => handleCopy("link")}
        className={`flex items-center gap-0 min-w-0 rounded-lg border transition-all cursor-pointer overflow-hidden group ${chipClass}`}
        title={t("clickToCopy")}
      >
        <span
          className={`px-2.5 py-1.5 text-xs font-mono truncate ${isExpired ? "text-error line-through" : "text-muted"}`}
        >
          {enrollLink}
        </span>
        <span className="flex items-center px-2 py-1.5 border-l border-border-soft text-muted-soft group-hover:text-kb transition-colors">
          {copied === "link" ? <Check size={13} weight="bold" className="text-success" /> : <Copy size={13} />}
        </span>
      </button>

      {/* The bare code, for reading out loud or putting on a slide. */}
      <button
        onClick={() => handleCopy("code")}
        className={`flex items-center gap-0 shrink-0 rounded-lg border transition-all cursor-pointer overflow-hidden group ${chipClass}`}
        title={t("clickToCopyCode")}
      >
        <span
          className={`px-2.5 py-1.5 text-xs font-mono font-medium tracking-wider ${isExpired ? "text-error line-through" : "text-foreground"}`}
        >
          {link.code}
        </span>
        <span className="flex items-center px-2 py-1.5 border-l border-border-soft text-muted-soft group-hover:text-kb transition-colors">
          {copied === "code" ? <Check size={13} weight="bold" className="text-success" /> : <Copy size={13} />}
        </span>
      </button>

      {copied && <span className="text-xs text-success font-medium whitespace-nowrap">{t("copied")}</span>}
      {!copied && (
        <span
          className={`inline-flex items-center gap-1 text-xs whitespace-nowrap ${isExpired ? "text-error" : "text-muted-soft"}`}
        >
          <CalendarBlank size={12} />
          {isExpired ? t("expired") : expiresDate ? t("untilDate", { date: expiresDate }) : t("unlimited")}
        </span>
      )}
      <IconButton
        onClick={() => onRequestDelete(link)}
        title={t("deleteLink")}
        className="ml-auto opacity-0 group-hover/row:opacity-100 transition-all"
      >
        <Trash size={13} />
      </IconButton>
    </div>
  );
}
