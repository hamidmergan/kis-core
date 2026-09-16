"use client";

import type { Icon } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";
import LinkBusy from "@/components/ui/LinkBusy";

interface Props {
  /** Without a target the tile only announces what is coming. */
  href?: string;
  icon: Icon;
  title: string;
  body: string;
  badge?: string;
  testId: string;
}

/** The whole tile is the link, hover only recolours the border. */
export function StartTile({ href, icon: Icon, title, body, badge, testId }: Props) {
  const shell =
    "flex items-center gap-4 border-2 border-[var(--tile-border)] rounded-2xl bg-[var(--tile-bg)] p-5 text-foreground";
  const inner = (
    <>
      <span
        className={`flex items-center justify-center w-14 h-14 shrink-0 rounded-full ${
          href ? "bg-kb text-on-accent" : "bg-surface-dim text-muted-soft"
        }`}
      >
        {href ? (
          <LinkBusy size="sm">
            <Icon size={28} weight="bold" aria-hidden="true" />
          </LinkBusy>
        ) : (
          <Icon size={28} weight="bold" aria-hidden="true" />
        )}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold tracking-[-0.01em]">{title}</span>
          {badge && (
            <span
              className="text-2xs font-medium px-1.5 py-0.5 rounded-full border border-border-soft"
              style={{ backgroundColor: "var(--badge-slate-bg)", color: "var(--badge-slate-fg)" }}
            >
              {badge}
            </span>
          )}
        </div>
        <p className="text-sm leading-[21px] text-foreground-soft mt-1">{body}</p>
      </div>
    </>
  );
  if (!href) {
    return (
      <div className={shell} style={{ boxShadow: "var(--shadow)" }} data-testid={testId}>
        {inner}
      </div>
    );
  }
  return (
    <Link
      href={href}
      className={`${shell} transition-colors hover:border-kb no-underline`}
      style={{ boxShadow: "var(--shadow)" }}
      data-testid={testId}
    >
      {inner}
    </Link>
  );
}
