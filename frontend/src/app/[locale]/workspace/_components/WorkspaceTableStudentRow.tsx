"use client";

import { useLocale, useTranslations } from "next-intl";
import { CalendarBlank, Lock } from "@phosphor-icons/react";
import { useRouter } from "@/i18n/navigation";
import Spinner from "@/components/ui/Spinner";
import { useNavTransition } from "@/components/ui/useNavTransition";
import WorkspaceMenu from "./WorkspaceMenu";
import type { KiTutorWorkspace } from "../_shared";

/** Row for an enrolled course, a switched-off one stays grey instead of disappearing. */
export default function WorkspaceTableStudentRow({
  workspace,
  onLeave,
  manageColumns = true,
}: {
  workspace: KiTutorWorkspace;
  onLeave?: (uuid: string) => void;
  /** Links and status columns exist, otherwise the status moves under the title. */
  manageColumns?: boolean;
}) {
  // Only whoever joined through the demo sees the badge and can leave here.
  const isDemo = !!workspace.via_demo;
  const t = useTranslations("workspace.list");
  const tDemo = useTranslations("workspace.demo");
  const locale = useLocale();
  const router = useRouter();
  const { pending: opening, navigate } = useNavTransition();
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

  const status = closed ? (
    <span
      className="inline-flex items-center gap-1 text-xs whitespace-nowrap font-medium"
      style={{ color: "var(--muted)" }}
      title={t("closedHint")}
    >
      <Lock size={12} weight="fill" />
      {t("closedBadge")}
    </span>
  ) : untilDate ? (
    <span className="inline-flex items-center gap-1 text-xs whitespace-nowrap" style={{ color: "var(--muted)" }}>
      <CalendarBlank size={12} />
      {t("untilDate", { date: untilDate })}
    </span>
  ) : null;

  const menu = isDemo && onLeave
    ? <WorkspaceMenu testId="demo-row-menu" onLeave={() => onLeave(workspace.uuid)} />
    : null;

  const open = () => { if (!closed) navigate(() => router.push(href)); };
  // Every way in is dropped instead of only disabled, the new tab included.
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
          {opening && <Spinner size="xs" color="current" className="flex-shrink-0" />}
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
          <span className="text-xs truncate block" style={{ color: "var(--muted)" }} title={workspace.description}>
            {workspace.description}
          </span>
        )}
        {!manageColumns && status && <span className="block mt-0.5">{status}</span>}
      </td>
      <td
        className={`pl-6 py-3 text-right tabular-nums text-foreground-soft ${manageColumns ? "pr-4" : "pr-1"} ${zellenKlasse}`}
        onClick={open}
      >
        {workspace.source_count}
      </td>
      {manageColumns && (
        <>
          <td className="pl-20 pr-4 py-3" />
          <td className={`pl-20 pr-4 py-3 ${zellenKlasse}`} onClick={open}>
            {status}
          </td>
        </>
      )}
      <td className={`pr-4 py-3 ${manageColumns ? "pl-20" : "pl-3"}`}>
        {menu && <div className="flex justify-center">{menu}</div>}
      </td>
    </tr>
  );
}
