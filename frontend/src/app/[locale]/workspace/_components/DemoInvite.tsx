"use client";

import { useTranslations } from "next-intl";
import { Files } from "@phosphor-icons/react";
import { InviteCard } from "./InviteCard";

interface Props {
  onOpen: () => void;
}

/** The same card as the tour invitation, for a module list that has nothing in it. */
export function DemoInvite({ onOpen }: Props) {
  const t = useTranslations("workspace.demoHint");

  return (
    <InviteCard
      icon={Files}
      title={t("title")}
      body={t("body")}
      className="rounded-xl p-4 flex items-start gap-3 text-left"
      data-testid="demo-invite"
    >
      <button
        type="button"
        data-testid="demo-hint-open"
        onClick={onOpen}
        className="btn-primary text-sm rounded-lg px-4 py-2"
      >
        {t("join")}
      </button>
    </InviteCard>
  );
}
