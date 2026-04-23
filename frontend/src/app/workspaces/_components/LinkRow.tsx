"use client";

import { useState } from "react";
import { CalendarBlank, Check, Copy, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import type { AccessLink } from "../_shared";

interface LinkRowProps {
  link: AccessLink;
  onRequestDelete: (link: AccessLink) => void;
}

export default function LinkRow({ link, onRequestDelete }: LinkRowProps) {
  const [copied, setCopied] = useState(false);
  const enrollLink = `${typeof window !== "undefined" ? window.location.origin : ""}/workspaces?code=${link.code}`;
  const expiresDate = link.expires_at
    ? new Date(link.expires_at).toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Berlin",
      })
    : null;
  const isExpired = link.expires_at ? new Date(link.expires_at) < new Date() : false;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(enrollLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="group/row flex items-center gap-2 min-w-0 -mx-2 px-2 py-1 rounded-lg hover:bg-gray-200/50 transition-colors">
      <button
        onClick={handleCopy}
        className={`flex items-center gap-0 min-w-0 rounded-lg border transition-all cursor-pointer overflow-hidden group ${
          isExpired
            ? "border-red-200 bg-red-50 hover:bg-red-100"
            : "border-gray-200 bg-gray-50 hover:bg-gray-100 hover:border-gray-300"
        }`}
        title="Klicken zum Kopieren"
      >
        <span
          className={`px-2.5 py-1.5 text-xs font-mono truncate ${isExpired ? "text-red-400 line-through" : "text-gray-500"}`}
        >
          {enrollLink}
        </span>
        <span className="flex items-center px-2 py-1.5 border-l border-gray-200 text-gray-400 group-hover:text-primary transition-colors">
          {copied ? <Check size={13} weight="bold" className="text-green-600" /> : <Copy size={13} />}
        </span>
      </button>
      {copied && <span className="text-xs text-green-600 font-medium whitespace-nowrap">Kopiert!</span>}
      {!copied && (
        <span
          className={`inline-flex items-center gap-1 text-xs whitespace-nowrap ${isExpired ? "text-red-400" : "text-gray-400"}`}
        >
          <CalendarBlank size={12} />
          {isExpired ? "abgelaufen" : expiresDate ? `bis ${expiresDate}` : "unbegrenzt"}
        </span>
      )}
      <IconButton
        onClick={() => onRequestDelete(link)}
        title="Link löschen"
        className="ml-auto opacity-0 group-hover/row:opacity-100 transition-all"
      >
        <Trash size={13} />
      </IconButton>
    </div>
  );
}
