"use client";

import { useState } from "react";
import { Copy, Check } from "@phosphor-icons/react";
import { copyTextFromPromise } from "@/lib/clipboard";

/** Copies a text and shows a check mark for a moment. */
export default function CopyTextButton({ text, copyLabel, copiedLabel }: {
  text: () => string;
  copyLabel: string;
  copiedLabel: string;
}) {
  const [copied, setCopied] = useState(false);

  function copy() {
    copyTextFromPromise(Promise.resolve(text()));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap"
    >
      {copied ? <Check size={16} weight="bold" /> : <Copy size={16} weight="bold" />}
      {copied ? copiedLabel : copyLabel}
    </button>
  );
}
