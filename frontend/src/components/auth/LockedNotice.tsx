"use client";

import { Lock } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";

type Variant = "aia" | "tool" | "workspaceCreate";

interface Props {
  variant: Variant;
  className?: string;
}

export default function LockedNotice({ variant, className }: Props) {
  const t = useTranslations("permissions.locked");
  return (
    <div
      role="status"
      className={`flex items-start gap-3 rounded-lg p-4 border ${className ?? ""}`}
      style={{
        background: "var(--surface-dim)",
        borderColor: "var(--border)",
        color: "var(--foreground)",
      }}
    >
      <Lock size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
      <span className="text-sm leading-relaxed">{t(variant)}</span>
    </div>
  );
}
