"use client";

import { useLocale, useTranslations } from "next-intl";
import { ArrowRight, CalendarBlank } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { useRouter } from "@/i18n/navigation";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import type { KiTutorWorkspace } from "../_shared";

/** A row for a workspace the user only learns from. Same table as the managed
 *  rows, minus every control that would 403 anyway: no status switch, no link
 *  list, no menu. */
export default function WorkspaceTableStudentRow({ workspace }: { workspace: KiTutorWorkspace }) {
  const t = useTranslations("workspace.list");
  const locale = useLocale();
  const labels = useWorkspaceLabel();
  const router = useRouter();

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

  const open = () => router.push(href);

  return (
    <tr
      className="border-b border-border-soft transition-colors hover:bg-surface"
      onMouseEnter={() => router.prefetch(href)}
    >
      <td className="px-4 py-3" />
      <td
        className="px-4 py-3 cursor-pointer w-full max-w-0"
        onClick={open}
        onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(`/${locale}${href}`, "_blank"); } }}
      >
        <span className="font-medium text-foreground-soft truncate block" title={workspace.title}>
          {workspace.title}
        </span>
        {workspace.description && (
          <span className="text-xs truncate block" style={{ color: "var(--muted)" }}>
            {workspace.description}
          </span>
        )}
      </td>
      <td
        className="px-4 py-3 text-right tabular-nums text-foreground-soft cursor-pointer"
        onClick={open}
      >
        {workspace.source_count}
      </td>
      <td className="px-4 py-3" />
      <td className="px-4 py-3 cursor-pointer" onClick={open}>
        {untilDate && (
          <span className="inline-flex items-center gap-1 text-xs whitespace-nowrap" style={{ color: "var(--muted)" }}>
            <CalendarBlank size={12} />
            {t("untilDate", { date: untilDate })}
          </span>
        )}
      </td>
      <td className="px-4 py-3" />
      <td className="px-4 py-3 cursor-pointer" onClick={open}>
        <div className="flex justify-end">
          <IconButton
            onClick={(e: React.MouseEvent) => { e.stopPropagation(); open(); }}
            title={t("openWorkspace", { label: labels.singular })}
          >
            <ArrowRight size={13} weight="bold" />
          </IconButton>
        </div>
      </td>
    </tr>
  );
}
