"use client";

import type { Icon } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";
import LinkBusy from "@/components/ui/LinkBusy";

interface Props {
  href: string;
  icon?: Icon;
  title: string;
  body: string;
  testId: string;
}

/** The whole tile is the link, hover only recolours the border. */
export function StartTile({ href, icon: Icon, title, body, testId }: Props) {
  return (
    <Link
      href={href}
      className="flex flex-1 items-center gap-4 border-2 border-[var(--tile-border)] rounded-2xl bg-[var(--tile-bg)] p-5 text-foreground transition-colors hover:border-kb no-underline"
      style={{ boxShadow: "var(--shadow)" }}
      data-testid={testId}
    >
      <span className="flex items-center justify-center w-14 h-14 shrink-0 rounded-full bg-kb text-on-accent">
        {/* While the link loads the spinner takes the icon's place, so the slot keeps its size either way. */}
        <LinkBusy size="sm">{Icon ? <Icon size={28} weight="bold" aria-hidden="true" /> : null}</LinkBusy>
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold tracking-[-0.01em]">{title}</span>
        </div>
        <p className="text-sm leading-[21px] text-foreground-soft mt-1">{body}</p>
      </div>
    </Link>
  );
}
