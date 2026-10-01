"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CalendarBlank, Lock, Star } from "@phosphor-icons/react";
import { useRouter } from "@/i18n/navigation";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import { useNavTransition } from "@/components/ui/useNavTransition";
import WorkspaceDescription from "./WorkspaceDescription";
import WorkspaceInfoModal from "./WorkspaceInfoModal";
import WorkspaceMenu from "./WorkspaceMenu";
import type { KiTutorWorkspace } from "../_shared";

/** Row for an enrolled course, a switched-off one stays grey instead of disappearing. */
export default function WorkspaceTableStudentRow({
  workspace,
  onLeave,
  onToggleFavorite,
  manageColumns = true,
}: {
  workspace: KiTutorWorkspace;
  onLeave?: (uuid: string) => void;
  onToggleFavorite: (uuid: string, newVal: boolean) => Promise<void>;
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
  const [favoriting, setFavoriting] = useState(false);
  const [showInfo, setShowInfo] = useState(false);

  async function toggleFavorite() {
    setFavoriting(true);
    await onToggleFavorite(workspace.uuid, !workspace.is_favorite);
    setFavoriting(false);
  }

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

  const hasInfo = Boolean(workspace.description);
  const menu = (isDemo && onLeave) || hasInfo
    ? (
      <WorkspaceMenu
        testId="demo-row-menu"
        favorite={workspace.is_favorite}
        onToggleFavorite={toggleFavorite}
        onInfo={hasInfo ? () => setShowInfo(true) : undefined}
        onLeave={isDemo && onLeave ? () => onLeave(workspace.uuid) : undefined}
      />
    )
    : null;

  const open = () => { if (!closed) navigate(() => router.push(href)); };
  // Every way in is dropped instead of only disabled, the new tab included.
  const zellenKlasse = closed ? "" : "cursor-pointer";

  return (
    <>
    {showInfo && workspace.description && (
      <WorkspaceInfoModal title={workspace.title} text={workspace.description} onClose={() => setShowInfo(false)} />
    )}
    <tr
      className={`grid grid-cols-[minmax(0,1fr)_auto] border-b border-border-soft transition-colors sm:table-row ${closed ? "" : "hover:bg-surface"}`}
      style={closed ? { opacity: 0.55 } : undefined}
      onMouseEnter={() => { if (!closed) router.prefetch(href); }}
    >
      <td
        className={`col-start-1 row-start-1 min-w-0 px-4 pt-3 pb-0 sm:w-full sm:max-w-0 sm:pb-3 ${zellenKlasse}`}
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
        {workspace.description && <WorkspaceDescription text={workspace.description} />}
        {/* Without a status column the state keeps its old place under the title on a desktop. */}
        {!manageColumns && status && <span className="hidden sm:block mt-0.5">{status}</span>}
      </td>
      <td
        className={`col-start-2 row-start-1 pl-2 pr-4 pt-3 pb-0 sm:pl-6 sm:pb-3 text-right tabular-nums text-foreground-soft ${manageColumns ? "sm:pr-4" : "sm:pr-1"} ${zellenKlasse}`}
        onClick={open}
      >
        {workspace.source_count}
      </td>
      {manageColumns && (
        <td className={`hidden sm:table-cell pl-20 pr-4 py-3 ${zellenKlasse}`} onClick={open}>
          {status}
        </td>
      )}
      <td
        className={`col-span-2 row-start-2 pl-4 pr-4 pt-1.5 pb-3 sm:pt-3 sm:pb-3 sm:pr-4 ${manageColumns ? "sm:pl-20" : "sm:pl-3"}`}
      >
        <div className="flex items-center justify-between gap-1.5 sm:justify-end">
          {/* A phone has no status column, so the state stands next to the menu instead. */}
          <span className="sm:hidden">{status}</span>
          <span className="flex items-center gap-1.5">
            <IconButton
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); toggleFavorite(); }}
              title={workspace.is_favorite ? t("favoriteRemove") : t("favoriteAdd")}
              className={workspace.is_favorite ? "text-kb-dark" : ""}
              disabled={favoriting}
              data-testid="workspace-favorite"
            >
              <Star size={13} weight={workspace.is_favorite ? "fill" : "bold"} />
            </IconButton>
            {menu}
          </span>
        </div>
      </td>
    </tr>
    </>
  );
}
