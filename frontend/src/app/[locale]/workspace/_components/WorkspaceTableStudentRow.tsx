"use client";

import { useLocale, useTranslations } from "next-intl";
import { CalendarBlank, Lock } from "@phosphor-icons/react";
import { useRouter } from "@/i18n/navigation";
import WorkspaceMenu from "./WorkspaceMenu";
import type { KiTutorWorkspace } from "../_shared";

/** A row for a workspace the user only learns from. Same table as the managed
 *  rows, minus every control that would 403 anyway: no status switch, no link
 *  list, no menu.
 *
 *  A workspace switched off by its owner keeps its row and says so. It used to
 *  drop out of the list without a word, which read like a deleted course. The
 *  row stays put, greyed and not clickable, and turns back into a normal one
 *  the moment the owner switches it on again. */
export default function WorkspaceTableStudentRow({
  workspace,
  onLeave,
}: {
  workspace: KiTutorWorkspace;
  onLeave?: (uuid: string) => void;
}) {
  // Nur wer ueber die Demo beigetreten ist, sieht das Abzeichen und kann hier raus.
  // Wer ueber einen richtigen Link im selben Kurs sitzt, sieht davon nichts.
  const isDemo = !!workspace.via_demo;
  const t = useTranslations("workspace.list");
  const tDemo = useTranslations("workspace.demo");
  const locale = useLocale();
  const router = useRouter();
  const closed = !workspace.is_active;

  const href = workspace.enrollment_id
    ? `/workspace/${workspace.uuid}?eid=${workspace.enrollment_id}`
    : `/workspace/${workspace.uuid}`;

  const untilDate = workspace.enrolled_until
    ? new Date(workspace.enrolled_until).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Berlin",
      })
    : null;

  const open = () => { if (!closed) router.push(href); };
  // Everything that would lead into the closed workspace is dropped, not just
  // disabled: no click, no prefetch, no middle-click into a new tab.
  const zellenKlasse = closed ? "" : "cursor-pointer";

  return (
    <tr
      className={`border-b border-border-soft transition-colors ${closed ? "" : "hover:bg-surface"}`}
      style={closed ? { opacity: 0.55 } : undefined}
      onMouseEnter={() => { if (!closed) router.prefetch(href); }}
    >
      <td
        className={`px-4 py-3 w-full max-w-0 ${zellenKlasse}`}
        onClick={open}
        onMouseDown={(e) => { if (!closed && e.button === 1) { e.preventDefault(); window.open(`/${locale}${href}`, "_blank"); } }}
      >
        <span className="font-medium text-foreground-soft truncate flex items-center gap-1.5" title={workspace.title}>
          <span className="truncate">{workspace.title}</span>
          {isDemo && (
            <span
              className="flex-shrink-0 text-3xs font-semibold px-1.5 py-0.5 rounded"
              style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
            >
              {tDemo("button")}
            </span>
          )}
        </span>
        {workspace.description && (
          <span className="text-xs truncate block" style={{ color: "var(--muted)" }}>
            {workspace.description}
          </span>
        )}
      </td>
      <td
        className={`pl-6 pr-4 py-3 text-right tabular-nums text-foreground-soft ${zellenKlasse}`}
        onClick={open}
      >
        {workspace.source_count}
      </td>
      <td className="pl-20 pr-4 py-3" />
      <td className={`pl-20 pr-4 py-3 ${zellenKlasse}`} onClick={open}>
        {closed ? (
          <span
            className="inline-flex items-center gap-1 text-xs whitespace-nowrap font-medium"
            style={{ color: "var(--muted)" }}
            title={t("closedHint")}
          >
            <Lock size={12} weight="fill" />
            {t("closedBadge")}
          </span>
        ) : untilDate && (
          <span className="inline-flex items-center gap-1 text-xs whitespace-nowrap" style={{ color: "var(--muted)" }}>
            <CalendarBlank size={12} />
            {t("untilDate", { date: untilDate })}
          </span>
        )}
      </td>
      <td className="pl-20 pr-4 py-3">
        {isDemo && onLeave && (
          <div className="flex justify-center">
            <WorkspaceMenu testId="demo-row-menu" onLeave={() => onLeave(workspace.uuid)} />
          </div>
        )}
      </td>
    </tr>
  );
}
