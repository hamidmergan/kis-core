"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import {
  ArrowRight,
  CalendarBlank,
  CaretRight,
  ChartBar,
  Check,
  Copy,
  DotsThreeVertical,
  Files,
  Link as LinkIcon,
  PencilSimple,
  Plus,
  Trash,
  X,
} from "@phosphor-icons/react";
import HelpTooltip from "@/components/ui/HelpTooltip";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import ExpandableText from "@/components/ui/ExpandableText";
import { useTopLoader } from "nextjs-toploader";
import { MAX_ACCESS_LINKS, type AccessLink, type KiTutorModule, type StudentModule } from "./_shared";
import CreateModuleModal from "./_components/CreateModuleModal";
import AddLinkModal from "./_components/AddLinkModal";
import EditModuleModal from "./_components/EditModuleModal";
import StatsModal from "./_components/StatsModal";
import LinkRow from "./_components/LinkRow";
import StudentView from "./_components/StudentView";

function ModuleTableRow({
  module,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: {
  module: KiTutorModule;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}) {
  const router = useRouter();
  const [toggling, setToggling] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [showAddLink, setShowAddLink] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteLinkConfirm, setDeleteLinkConfirm] = useState<AccessLink | null>(null);
  const [deletingLink, setDeletingLink] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  const loader = useTopLoader();
  const links = module.access_links ?? [];
  const moduleHref = `/workspaces/${module.uuid}`;

  const handleOpen = () => { loader.start(); router.push(moduleHref); };
  const handlePrefetch = () => router.prefetch(moduleHref);

  async function handleToggle(newVal: boolean) {
    setToggling(true);
    await onToggleActive(module.uuid, newVal);
    setToggling(false);
  }

  async function handleDeleteConfirm() {
    setDeleting(true);
    await onDelete(module.uuid);
    setDeleteConfirm(false);
    setDeleting(false);
  }

  async function handleDeleteLinkConfirm() {
    if (!deleteLinkConfirm) return;
    setDeletingLink(true);
    try {
      const res = await fetch(`/api/ki-assistent/modules/${module.uuid}/access-links/${deleteLinkConfirm.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        onLinksChanged(module.uuid, links.filter((l) => l.id !== deleteLinkConfirm.id));
      }
      setDeleteLinkConfirm(null);
    } finally {
      setDeletingLink(false);
    }
  }

  function handleLinkCreated(newLink: AccessLink) {
    onLinksChanged(module.uuid, [...links, newLink]);
  }

  return (
    <>
      {showStats && (
        <StatsModal moduleUuid={module.uuid} moduleTitle={module.title} onClose={() => setShowStats(false)} />
      )}
      {editOpen && (
        <EditModuleModal
          currentTitle={module.title}
          currentDescription={module.description ?? ""}
          onClose={() => setEditOpen(false)}
          onSubmit={(t, d) => onEdit(module.uuid, t, d)}
        />
      )}
      {showAddLink && (
        <AddLinkModal moduleUuid={module.uuid} onClose={() => setShowAddLink(false)} onCreated={handleLinkCreated} />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Workspace löschen?</h3>
            <p className="text-sm text-gray-600 mb-1"><span className="font-medium">{module.title}</span></p>
            <p className="text-sm text-red-600 mb-6">Der Workspace und alle zugehörigen Daten werden unwiderruflich gelöscht.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteConfirm(false)} disabled={deleting} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">Abbrechen</button>
              <button onClick={handleDeleteConfirm} disabled={deleting} className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50">{deleting ? "..." : "Löschen"}</button>
            </div>
          </div>
        </div>
      )}
      {deleteLinkConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Einschreibelink löschen?</h3>
            <p className="text-sm text-gray-600 mb-1">
              <span className="font-medium">...{deleteLinkConfirm.code}</span> – {deleteLinkConfirm.expires_at ? `gültig bis ${new Date(deleteLinkConfirm.expires_at).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" })}` : "unbegrenzt gültig"}
            </p>
            <p className="text-sm text-red-600 mb-6">Der Link wird ungültig. Bereits eingeschriebene Studierende behalten ihren Zugang.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteLinkConfirm(null)} disabled={deletingLink} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">Abbrechen</button>
              <button onClick={handleDeleteLinkConfirm} disabled={deletingLink} className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50">{deletingLink ? "..." : "Löschen"}</button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop: table row */}
      <tr
        className="group hidden md:table-row border-t transition-colors"
        style={{
          borderColor: "var(--border)",
          backgroundColor: expanded ? "var(--surface)" : undefined,
        }}
        onMouseEnter={handlePrefetch}
      >
        <td className="py-5 cursor-pointer" onClick={() => setExpanded(!expanded)}>
          <div className="flex justify-center">
            <IconButton
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); setExpanded(!expanded); }}
              title={expanded ? "Zuklappen" : "Aufklappen"}
            >
              <CaretRight size={13} weight="bold" className={`transition-transform ${expanded ? "rotate-90" : ""}`} />
            </IconButton>
          </div>
        </td>
        <td
          className="pr-6 py-5 cursor-pointer"
          onClick={handleOpen}
          onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); window.open(moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "#FAFBFC"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="min-w-0">
            <div className="text-[15px] font-semibold text-gray-900 truncate">{module.title}</div>
          </div>
        </td>
        <td
          className="px-6 py-5 text-[15px] font-medium tabular-nums text-gray-900 cursor-pointer"
          onClick={handleOpen}
          onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); window.open(moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "#FAFBFC"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          {module.source_count}
        </td>
        <td
          className="px-6 py-5 text-[15px] font-medium tabular-nums text-gray-900 cursor-pointer"
          onClick={handleOpen}
          onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); window.open(moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "#FAFBFC"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          {links.length}
        </td>
        <td
          className="px-6 py-5 cursor-pointer"
          onClick={() => !toggling && handleToggle(!module.is_active)}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "#FAFBFC"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              role="switch"
              aria-checked={module.is_active}
              aria-label={module.is_active ? "Workspace deaktivieren" : "Workspace aktivieren"}
              onClick={(e) => { e.stopPropagation(); handleToggle(!module.is_active); }}
              disabled={toggling}
              className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2"
              style={{
                backgroundColor: module.is_active ? "var(--kb)" : "#d1d5db",
                ...(module.is_active && { boxShadow: "0 0 0 0 var(--kb)" }),
              }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                  module.is_active ? "translate-x-[18px]" : "translate-x-0.5"
                }`}
              />
            </button>
            <span
              className="text-xs font-medium"
              style={{ color: module.is_active ? "var(--kb)" : "#6b7280" }}
            >
              {module.is_active ? "Aktiv" : "Inaktiv"}
            </span>
          </div>
        </td>
        <td
          className="py-5 text-center relative cursor-pointer"
          onClick={() => setShowMenu(!showMenu)}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "#FAFBFC"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex justify-center">
            <IconButton onClick={(e: React.MouseEvent) => { e.stopPropagation(); setShowMenu(!showMenu); }} title="Mehr">
              <DotsThreeVertical size={13} weight="bold" />
            </IconButton>
          </div>
          {showMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
              <div
                className="absolute right-2 top-12 z-50 rounded-xl py-1"
                style={{
                  backgroundColor: "var(--surface)",
                  border: "1px solid var(--border)",
                  minWidth: 220,
                  boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                }}
              >
                <button
                  type="button"
                  onClick={() => { setShowMenu(false); setShowStats(true); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 transition-colors"
                  style={{ color: "var(--text)" }}
                >
                  <ChartBar size={16} />
                  Statistik
                </button>
                <button
                  type="button"
                  onClick={() => { setShowMenu(false); setEditOpen(true); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 transition-colors"
                  style={{ color: "var(--text)" }}
                >
                  <PencilSimple size={16} />
                  Bearbeiten
                </button>
                <button
                  type="button"
                  onClick={() => { setShowMenu(false); setDeleteConfirm(true); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 transition-colors"
                  style={{ color: "rgb(185, 28, 28)" }}
                >
                  <Trash size={16} />
                  Löschen
                </button>
              </div>
            </>
          )}
        </td>
        <td
          className="pr-2 py-5 cursor-pointer"
          onClick={handleOpen}
          onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); window.open(moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "#FAFBFC"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex justify-end">
            <IconButton
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); handleOpen(); }}
              title="Workspace öffnen"
            >
              <ArrowRight size={13} weight="bold" />
            </IconButton>
          </div>
        </td>
      </tr>

      {/* Desktop: expanded row */}
      {expanded && (
        <tr className="hidden md:table-row" style={{ backgroundColor: "var(--surface)" }}>
          <td colSpan={7} className="pl-11 pr-6 pb-5" style={{ borderTop: "none" }}>
            <div className="flex flex-col gap-3 max-w-full break-words">
              {module.description && (
                <p className="text-[13px] leading-relaxed break-words" style={{ color: "var(--muted)" }}>
                  {module.description}
                </p>
              )}
              {links.map((link) => (
                <LinkRow key={link.id} link={link} onRequestDelete={setDeleteLinkConfirm} />
              ))}
              {links.length >= MAX_ACCESS_LINKS ? (
                <p className="text-xs self-start mt-0.5" style={{ color: "var(--muted)" }}>
                  Maximal {MAX_ACCESS_LINKS} Einschreibelinks erreicht. Lösche einen alten Link, um einen neuen zu erstellen.
                </p>
              ) : (
                <button
                  onClick={() => setShowAddLink(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-primary transition-colors self-start mt-0.5"
                >
                  <Plus size={12} weight="bold" />
                  Neuer Link
                </button>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Mobile Module Card ──────────────────────────────────────────────────────

function ModuleCard({
  module,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: {
  module: KiTutorModule;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}) {
  const router = useRouter();
  const [toggling, setToggling] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [showAddLink, setShowAddLink] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteLinkConfirm, setDeleteLinkConfirm] = useState<AccessLink | null>(null);
  const [deletingLink, setDeletingLink] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  const loader = useTopLoader();
  const links = module.access_links ?? [];
  const moduleHref = `/workspaces/${module.uuid}`;
  const handleOpen = () => { loader.start(); router.push(moduleHref); };
  const handlePrefetch = () => router.prefetch(moduleHref);

  async function handleToggle(newVal: boolean) {
    setToggling(true);
    await onToggleActive(module.uuid, newVal);
    setToggling(false);
  }

  async function handleDeleteConfirm() {
    setDeleting(true);
    await onDelete(module.uuid);
    setDeleteConfirm(false);
    setDeleting(false);
  }

  async function handleDeleteLinkConfirm() {
    if (!deleteLinkConfirm) return;
    setDeletingLink(true);
    try {
      const res = await fetch(`/api/ki-assistent/modules/${module.uuid}/access-links/${deleteLinkConfirm.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        onLinksChanged(module.uuid, links.filter((l) => l.id !== deleteLinkConfirm.id));
      }
      setDeleteLinkConfirm(null);
    } finally {
      setDeletingLink(false);
    }
  }

  return (
    <>
      {showStats && (
        <StatsModal moduleUuid={module.uuid} moduleTitle={module.title} onClose={() => setShowStats(false)} />
      )}
      {editOpen && (
        <EditModuleModal
          currentTitle={module.title}
          currentDescription={module.description ?? ""}
          onClose={() => setEditOpen(false)}
          onSubmit={(t, d) => onEdit(module.uuid, t, d)}
        />
      )}
      {showAddLink && (
        <AddLinkModal moduleUuid={module.uuid} onClose={() => setShowAddLink(false)} onCreated={(newLink) => onLinksChanged(module.uuid, [...links, newLink])} />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Workspace löschen?</h3>
            <p className="text-sm text-gray-600 mb-1"><span className="font-medium">{module.title}</span></p>
            <p className="text-sm text-red-600 mb-6">Der Workspace und alle zugehörigen Daten werden unwiderruflich gelöscht.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteConfirm(false)} disabled={deleting} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">Abbrechen</button>
              <button onClick={handleDeleteConfirm} disabled={deleting} className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50">{deleting ? "..." : "Löschen"}</button>
            </div>
          </div>
        </div>
      )}
      {deleteLinkConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Einschreibelink löschen?</h3>
            <p className="text-sm text-gray-600 mb-1">
              <span className="font-medium">...{deleteLinkConfirm.code}</span> – {deleteLinkConfirm.expires_at ? `gültig bis ${new Date(deleteLinkConfirm.expires_at).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" })}` : "unbegrenzt gültig"}
            </p>
            <p className="text-sm text-red-600 mb-6">Der Link wird ungültig. Bereits eingeschriebene Studierende behalten ihren Zugang.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteLinkConfirm(null)} disabled={deletingLink} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">Abbrechen</button>
              <button onClick={handleDeleteLinkConfirm} disabled={deletingLink} className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50">{deletingLink ? "..." : "Löschen"}</button>
            </div>
          </div>
        </div>
      )}

      <div
        className="border-t"
        style={{
          borderColor: "var(--border)",
          backgroundColor: expanded ? "var(--surface)" : undefined,
        }}
        onTouchStart={handlePrefetch}
      >
        {/* Top row: chevron + title (full width) */}
        <div className="flex items-center gap-2 pt-4 pb-2 pl-2">
          <IconButton
            onClick={() => setExpanded(!expanded)}
            title={expanded ? "Zuklappen" : "Aufklappen"}
          >
            <CaretRight size={13} weight="bold" className={`transition-transform ${expanded ? "rotate-90" : ""}`} />
          </IconButton>
          <button
            type="button"
            onClick={handleOpen}
            onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); window.open(moduleHref, "_blank"); } }}
            className="flex-1 min-w-0 text-left"
          >
            <div className="text-[15px] font-semibold text-gray-900 break-words">{module.title}</div>
          </button>
        </div>

        {/* Meta row: status toggle + counts + 3-dots + arrow */}
        <div className="flex items-center gap-3 pl-[52px] pr-2 pb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <button
              type="button"
              role="switch"
              aria-checked={module.is_active}
              aria-label={module.is_active ? "Workspace deaktivieren" : "Workspace aktivieren"}
              onClick={() => handleToggle(!module.is_active)}
              disabled={toggling}
              className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2"
              style={{ backgroundColor: module.is_active ? "var(--kb)" : "#d1d5db" }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                  module.is_active ? "translate-x-[18px]" : "translate-x-0.5"
                }`}
              />
            </button>
            <span
              className="text-xs font-medium"
              style={{ color: module.is_active ? "var(--kb)" : "#6b7280" }}
            >
              {module.is_active ? "Aktiv" : "Inaktiv"}
            </span>
          </div>
          <span className="text-xs" style={{ color: "var(--muted)" }}>{module.source_count} Quellen</span>
          <span className="text-xs" style={{ color: "var(--muted)" }}>{links.length} Links</span>
          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <IconButton onClick={() => setShowMenu(!showMenu)} title="Mehr">
                <DotsThreeVertical size={13} weight="bold" />
              </IconButton>
              {showMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
                  <div
                    className="absolute right-0 top-9 z-50 rounded-xl py-1"
                    style={{
                      backgroundColor: "var(--surface)",
                      border: "1px solid var(--border)",
                      minWidth: 220,
                      boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => { setShowMenu(false); setShowStats(true); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 transition-colors"
                      style={{ color: "var(--text)" }}
                    >
                      <ChartBar size={16} />
                      Statistik
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowMenu(false); setEditOpen(true); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 transition-colors"
                      style={{ color: "var(--text)" }}
                    >
                      <PencilSimple size={16} />
                      Bearbeiten
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowMenu(false); setDeleteConfirm(true); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-black/5 transition-colors"
                      style={{ color: "rgb(185, 28, 28)" }}
                    >
                      <Trash size={16} />
                      Löschen
                    </button>
                  </div>
                </>
              )}
            </div>
            <IconButton onClick={handleOpen} title="Workspace öffnen">
              <ArrowRight size={13} weight="bold" />
            </IconButton>
          </div>
        </div>

        {/* Expanded: description + links */}
        {expanded && (
          <div className="flex flex-col gap-3 pl-[52px] pr-2 pb-5">
            {module.description && (
              <p className="text-[13px] leading-relaxed break-words" style={{ color: "var(--muted)" }}>
                {module.description}
              </p>
            )}
            {links.map((link) => (
              <LinkRow key={link.id} link={link} onRequestDelete={setDeleteLinkConfirm} />
            ))}
            {links.length >= MAX_ACCESS_LINKS ? (
              <p className="text-xs self-start mt-0.5" style={{ color: "var(--muted)" }}>
                Maximal {MAX_ACCESS_LINKS} Einschreibelinks erreicht. Lösche einen alten Link, um einen neuen zu erstellen.
              </p>
            ) : (
              <button
                onClick={() => setShowAddLink(true)}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-primary transition-colors self-start mt-0.5"
              >
                <Plus size={12} weight="bold" />
                Neuer Link
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}

const MODULES_PER_PAGE = 20;

function ModuleTable({
  modules,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: {
  modules: KiTutorModule[];
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(modules.length / MODULES_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * MODULES_PER_PAGE;
  const visibleModules = modules.slice(startIdx, startIdx + MODULES_PER_PAGE);
  return (
    <>
      {/* Desktop: table */}
      <div className="hidden md:block w-full">
        <table className="w-full" style={{ tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: "44px" }} />
            <col />
            <col style={{ width: "100px" }} />
            <col style={{ width: "100px" }} />
            <col style={{ width: "140px" }} />
            <col style={{ width: "52px" }} />
            <col style={{ width: "44px" }} />
          </colgroup>
          <thead>
            <tr>
              <th className="pb-3"></th>
              <th className="text-left pr-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Workspace</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Quellen</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Links</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>
                <span className="inline-flex items-center gap-1.5">
                  Status
                  <HelpTooltip text="Aktiv: Studierende können sich über Zugangslinks in den Workspace einschreiben und die Inhalte nutzen. Inaktiv: Der Workspace ist für Studierende gesperrt. Bestehende Einschreibungen bleiben erhalten." />
                </span>
              </th>
              <th className="pb-3"></th>
              <th className="pr-2 pb-3"></th>
            </tr>
          </thead>
          <tbody>
            {visibleModules.map((m) => (
              <ModuleTableRow
                key={m.uuid}
                module={m}
                onToggleActive={onToggleActive}
                onDelete={onDelete}
                onEdit={onEdit}
                onLinksChanged={onLinksChanged}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile: cards */}
      <div className="md:hidden">
        {visibleModules.map((m) => (
          <ModuleCard
            key={m.uuid}
            module={m}
            onToggleActive={onToggleActive}
            onDelete={onDelete}
            onEdit={onEdit}
            onLinksChanged={onLinksChanged}
          />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            Zeige {startIdx + 1} bis {Math.min(startIdx + MODULES_PER_PAGE, modules.length)} von {modules.length} Workspaces
          </p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage(safePage - 1)}
              disabled={safePage === 1}
              className="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed hover:bg-black/5"
              style={{ color: "var(--text)" }}
            >
              Zurück
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPage(p)}
                className="w-8 h-8 text-sm font-medium rounded-lg transition-colors"
                style={{
                  backgroundColor: p === safePage ? "var(--kb)" : "transparent",
                  color: p === safePage ? "white" : "var(--text)",
                }}
              >
                {p}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setPage(safePage + 1)}
              disabled={safePage === totalPages}
              className="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed hover:bg-black/5"
              style={{ color: "var(--text)" }}
            >
              Weiter
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function LecturerView() {
  const [modules, setModules] = useState<KiTutorModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const loadModules = useCallback(async () => {
    try {
      const res = await fetch("/api/ki-assistent/modules", { credentials: "include" });
      if (res.ok) setModules(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadModules().finally(() => setLoading(false));
  }, [loadModules]);

  // Poll every 3s while any module is pending or indexing
  useEffect(() => {
    const needsPoll = modules.some((m) => m.status === "pending" || m.status === "indexing");
    if (!needsPoll) return;
    const id = setInterval(loadModules, 3000);
    return () => clearInterval(id);
  }, [modules, loadModules]);

  async function handleToggleActive(uuid: string, newVal: boolean) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: newVal }),
      });
      if (res.ok) {
        setModules((prev) => prev.map((m) => m.uuid === uuid ? { ...m, is_active: newVal } : m));
      }
    } catch { /* ignore */ }
  }

  async function handleDelete(uuid: string) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        setModules((prev) => prev.filter((m) => m.uuid !== uuid));
      }
    } catch { /* ignore */ }
  }

  async function handleEdit(uuid: string, newTitle: string, newDescription: string): Promise<boolean> {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle, description: newDescription }),
      });
      if (res.ok) {
        setModules((prev) => prev.map((m) => m.uuid === uuid ? { ...m, title: newTitle, description: newDescription || null } : m));
        return true;
      }
    } catch { /* ignore */ }
    return false;
  }

  function handleLinksChanged(uuid: string, links: AccessLink[]) {
    setModules((prev) =>
      prev.map((m) => m.uuid === uuid ? { ...m, access_links: links } : m)
    );
  }

  return (
    <>
      {showCreate && (
        <CreateModuleModal
          onClose={() => setShowCreate(false)}
          onCreated={(m) => setModules((prev) => [m, ...prev])}
        />
      )}

      <div className="mb-3">
        <h1 className="text-3xl font-bold mb-10">Willkommen bei KIS</h1>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Meine Workspaces</h2>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-primary"
          >
            + Neuer Workspace
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Spinner size="lg" />
        </div>
      ) : modules.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20" style={{ color: "var(--muted)" }}>
          <Files size={40} weight="duotone" className="mb-3 opacity-40" />
          <p className="text-base">Noch keine Workspaces vorhanden.</p>
          <p className="text-sm mt-1">Erstelle deinen ersten Workspace mit dem Button oben.</p>
        </div>
      ) : (
        <div className="mt-6 md:mt-20">
          <ModuleTable
            modules={modules}
            onToggleActive={handleToggleActive}
            onDelete={handleDelete}
            onEdit={handleEdit}
            onLinksChanged={handleLinksChanged}
          />
        </div>
      )}
    </>
  );
}

// ─── Student View ─────────────────────────────────────────────────────────────


// ─── Page ─────────────────────────────────────────────────────────────────────

export default function KiTutorPage() {
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => setRole(s.role ?? "lecturer"));
  }, []);

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
        {role !== null && (role === "lecturer" ? <LecturerView /> : <Suspense><StudentView /></Suspense>)}
      </div>
    </ProtectedRoute>
  );
}
