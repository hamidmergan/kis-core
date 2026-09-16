"use client";

import { useTranslations } from "next-intl";
import { Files } from "@phosphor-icons/react";

interface Props {
  onOpen: () => void;
}

/** The same card as the tour invitation, for a module list that has nothing in it. */
export function DemoInvite({ onOpen }: Props) {
  const t = useTranslations("workspace.demoHint");

  return (
    <div
      className="rounded-xl p-4 flex items-start gap-3 text-left"
      style={{ backgroundColor: "var(--surface-dim)", border: "1px solid var(--border-soft)" }}
      data-testid="demo-invite"
    >
      <Files size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0, marginTop: 2 }} />
      <div className="min-w-0 flex-1 self-stretch flex flex-col">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("title")}</p>
        <p className="text-sm mt-1" style={{ color: "var(--foreground-soft)" }}>{t("body")}</p>
        <div className="flex items-stretch gap-2 mt-auto pt-3">
          <button
            type="button"
            data-testid="demo-hint-open"
            onClick={onOpen}
            className="btn-primary text-sm rounded-lg px-4 py-2"
          >
            {t("join")}
          </button>
        </div>
      </div>
    </div>
  );
}
