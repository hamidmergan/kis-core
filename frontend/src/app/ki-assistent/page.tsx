"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
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
  Plus,
  Trash,
  X,
} from "@phosphor-icons/react";
import HelpTooltip from "@/components/HelpTooltip";
import IconButton from "@/components/IconButton";
import Spinner from "@/components/Spinner";

const MAX_ACCESS_LINKS = 10;

// ─── Types ────────────────────────────────────────────────────────────────────

interface AccessLink {
  id: number;
  code: string;
  expires_at: string | null;
  created_at?: string | null;
}

interface KiTutorModule {
  uuid: string;
  title: string;
  description?: string | null;
  status: "pending" | "indexing" | "ready" | "failed";
  source_count: number;
  is_active: boolean;
  access_links?: AccessLink[];
  // Legacy
  enroll_code: string | null;
  enroll_code_expires: string | null;
  created_at: string | null;
}

interface StudentModule {
  uuid: string;
  title: string;
  description?: string | null;
  status: string;
  enrollment_id?: number | null;
  enrolled_until?: string | null;
  created_at: string | null;
}

// ─── Create Module Modal ──────────────────────────────────────────────────────

function CreateModuleModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (m: KiTutorModule) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("title", title.trim());
      if (description.trim()) form.append("description", description.trim());
      if (expiresAt) form.append("expires_at", new Date(expiresAt).toISOString());
      const res = await fetch("/api/ki-assistent/modules", {
        method: "POST",
        credentials: "include",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Fehler beim Erstellen");
      }
      const created = await res.json();
      onCreated({
        uuid: created.uuid,
        title: title.trim(),
        description: description.trim() || null,
        status: "pending",
        source_count: 0,
        is_active: false,
        access_links: created.access_links ?? [],
        enroll_code: created.enroll_code ?? null,
        enroll_code_expires: created.enroll_code_expires ?? null,
        created_at: new Date().toISOString(),
      });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-md rounded-xl p-6 shadow-xl"
        style={{ backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-lg font-semibold mb-5">
          Neuen Arbeitsraum erstellen
        </h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Titel <span style={{ color: "#E11D48" }}>*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value.slice(0, 50))}
              required
              maxLength={50}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
              placeholder="z. B. Einführung in die Informatik"
            />
            <p className="text-xs text-gray-400 text-right mt-1">{title.length}/50</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Beschreibung
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value.slice(0, 300))}
              maxLength={300}
              rows={2}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none resize-none"
              style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
              placeholder="z. B. Sommersemester 2026, Grundlagen der Programmierung"
            />
            <p className="text-xs text-gray-400 text-right mt-1">{description.length}/300</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Einschreibecode gültig bis
            </label>
            <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              min={new Date().toISOString().split("T")[0]}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
            />
          </div>
          {error && <p className="text-sm" style={{ color: "#E11D48" }}>{error}</p>}
          <div className="flex gap-3 justify-end mt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium"
              style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={loading || !title.trim()}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 bg-primary"
            >
              {loading ? "Erstellen…" : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Add Link Modal ──────────────────────────────────────────────────────────

function AddLinkModal({
  moduleUuid,
  onClose,
  onCreated,
}: {
  moduleUuid: string;
  onClose: () => void;
  onCreated: (link: AccessLink) => void;
}) {
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!expiresAt) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/ki-assistent/modules/${moduleUuid}/access-links`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expires_at: new Date(expiresAt).toISOString() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Fehler beim Erstellen");
      }
      const data = await res.json();
      onCreated(data);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-sm rounded-xl p-6 shadow-xl"
        style={{ backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-lg font-semibold mb-2">
          Neuen Einschreibelink erstellen
        </h2>
        <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
          Jeder Link hat eine eigene Laufzeit. Studierende mit unterschiedlichen Links haben getrennte Chat-Verläufe.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Gültig bis
            </label>
            <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              required
              min={new Date().toISOString().split("T")[0]}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
            />
          </div>
          {error && <p className="text-sm" style={{ color: "#E11D48" }}>{error}</p>}
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium"
              style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={loading || !expiresAt}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 bg-primary"
            >
              {loading ? "Erstellen…" : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Expandable Text ────────────────────────────────────────────────────────

function ExpandableText({ children, className = "", clampClass = "", style }: { children: React.ReactNode; className?: string; clampClass?: string; style?: React.CSSProperties }) {
  const [expanded, setExpanded] = useState(false);
  const [isClamped, setIsClamped] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) setIsClamped(el.scrollHeight > el.clientHeight + 1);
  }, [children]);

  return (
    <p
      ref={ref}
      className={`${className} ${expanded ? "" : clampClass} ${isClamped || expanded ? "cursor-pointer" : ""}`}
      style={style}
      onClick={isClamped || expanded ? (e) => { e.stopPropagation(); setExpanded(!expanded); } : undefined}
      title={isClamped || expanded ? (expanded ? "Klicken zum Einklappen" : "Klicken zum Aufklappen") : undefined}
    >
      {children}
    </p>
  );
}

// ─── Link Row (per Access Link) ──────────────────────────────────────────────

function LinkRow({ link, onRequestDelete }: { link: AccessLink; onRequestDelete: (link: AccessLink) => void }) {
  const [copied, setCopied] = useState(false);
  const enrollLink = `${typeof window !== "undefined" ? window.location.origin : ""}/ki-assistent?code=${link.code}`;
  const expiresDate = link.expires_at
    ? new Date(link.expires_at).toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Berlin",
      })
    : null;
  const isExpired = link.expires_at ? new Date(link.expires_at) < new Date() : false;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(enrollLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  }

  return (
    <div className="group/row flex items-center gap-2 min-w-0 -mx-2 px-2 py-1 rounded-lg hover:bg-gray-200/50 transition-colors">
      <button
        onClick={handleCopy}
        className={`flex items-center gap-0 min-w-0 rounded-lg border transition-all cursor-pointer overflow-hidden group ${
          isExpired
            ? "border-red-200 bg-red-50 hover:bg-red-100"
            : "border-gray-200 bg-gray-50 hover:bg-gray-100 hover:border-gray-300"
        }`}
        title="Klicken zum Kopieren"
      >
        <span className={`px-2.5 py-1.5 text-xs font-mono truncate ${isExpired ? "text-red-400 line-through" : "text-gray-500"}`}>
          {enrollLink}
        </span>
        <span className="flex items-center px-2 py-1.5 border-l border-gray-200 text-gray-400 group-hover:text-primary transition-colors">
          {copied ? (
            <Check size={13} weight="bold" className="text-green-600" />
          ) : (
            <Copy size={13} />
          )}
        </span>
      </button>
      {copied && <span className="text-xs text-green-600 font-medium whitespace-nowrap">Kopiert!</span>}
      {!copied && (
        <span className={`inline-flex items-center gap-1 text-xs whitespace-nowrap ${isExpired ? "text-red-400" : "text-gray-400"}`}>
          <CalendarBlank size={12} />
          {isExpired ? "abgelaufen" : expiresDate ? `bis ${expiresDate}` : "unbegrenzt"}
        </span>
      )}
      <IconButton
        onClick={() => onRequestDelete(link)}
        title="Link löschen"
        className="ml-auto opacity-0 group-hover/row:opacity-100 transition-all"
      >
        <Trash size={13} />
      </IconButton>
    </div>
  );
}

// ─── Stats Modal ─────────────────────────────────────────────────────────────

interface ModuleStats {
  overview: {
    total_enrolled: number;
    active_30d: number;
    total_chat_messages: number;
    total_exercise_sets: number;
  };
}

function StatsModal({ moduleUuid, moduleTitle, onClose }: { moduleUuid: string; moduleTitle: string; onClose: () => void }) {
  const [stats, setStats] = useState<ModuleStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ki-assistent/modules/${moduleUuid}/dozent-stats`, { credentials: "include" });
        if (!res.ok) throw new Error("Fehler beim Laden");
        setStats(await res.json());
      } catch {
        setError("Statistiken konnten nicht geladen werden.");
      } finally {
        setLoading(false);
      }
    })();
  }, [moduleUuid]);

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-80" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-sm font-semibold">Statistik</h2>
          <IconButton onClick={onClose}>
            <X size={13} weight="bold" />
          </IconButton>
        </div>

        {/* Body */}
        <div className="p-4">
          {loading && <p className="text-sm text-gray-500 text-center py-4">Laden...</p>}
          {error && <p className="text-sm text-red-600 text-center py-4">{error}</p>}

          {stats && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "Teilnehmer", value: stats.overview.total_enrolled },
                { label: "Aktiv (30 Tage)", value: stats.overview.active_30d },
                { label: "Chat-Anfragen", value: stats.overview.total_chat_messages },
                { label: "Erstellte Übungen", value: stats.overview.total_exercise_sets },
              ].map((item) => (
                <div key={item.label} className="bg-gray-50 rounded-lg px-3 py-2.5">
                  <div className="text-xs text-gray-500">{item.label}</div>
                  <div className="text-lg font-semibold mt-0.5" style={{ color: "var(--text)" }}>{item.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Lecturer View ────────────────────────────────────────────────────────────

function ModuleTableRow({
  module,
  onToggleActive,
  onDelete,
  onLinksChanged,
}: {
  module: KiTutorModule;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
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

  const links = module.access_links ?? [];

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
      {showAddLink && (
        <AddLinkModal moduleUuid={module.uuid} onClose={() => setShowAddLink(false)} onCreated={handleLinkCreated} />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Arbeitsraum löschen?</h3>
            <p className="text-sm text-gray-600 mb-1"><span className="font-medium">{module.title}</span></p>
            <p className="text-sm text-red-600 mb-6">Der Arbeitsraum und alle zugehörigen Daten werden unwiderruflich gelöscht.</p>
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
          onClick={() => router.push(`/ki-assistent/${module.uuid}`)}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="min-w-0">
            <div className="text-[15px] font-semibold text-gray-900 truncate">{module.title}</div>
          </div>
        </td>
        <td
          className="px-6 py-5 text-[15px] font-medium tabular-nums text-gray-900 cursor-pointer"
          onClick={() => router.push(`/ki-assistent/${module.uuid}`)}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          {module.source_count}
        </td>
        <td
          className="px-6 py-5 text-[15px] font-medium tabular-nums text-gray-900 cursor-pointer"
          onClick={() => router.push(`/ki-assistent/${module.uuid}`)}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          {links.length}
        </td>
        <td
          className="px-6 py-5 cursor-pointer"
          onClick={() => !toggling && handleToggle(!module.is_active)}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              role="switch"
              aria-checked={module.is_active}
              aria-label={module.is_active ? "Arbeitsraum deaktivieren" : "Arbeitsraum aktivieren"}
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
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
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
          onClick={() => router.push(`/ki-assistent/${module.uuid}`)}
          onMouseEnter={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex justify-end">
            <IconButton
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); router.push(`/ki-assistent/${module.uuid}`); }}
              title="Arbeitsraum öffnen"
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
                  Neuen Link erstellen
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
  onLinksChanged,
}: {
  module: KiTutorModule;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
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

  const links = module.access_links ?? [];

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
      {showAddLink && (
        <AddLinkModal moduleUuid={module.uuid} onClose={() => setShowAddLink(false)} onCreated={(newLink) => onLinksChanged(module.uuid, [...links, newLink])} />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Arbeitsraum löschen?</h3>
            <p className="text-sm text-gray-600 mb-1"><span className="font-medium">{module.title}</span></p>
            <p className="text-sm text-red-600 mb-6">Der Arbeitsraum und alle zugehörigen Daten werden unwiderruflich gelöscht.</p>
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
            onClick={() => router.push(`/ki-assistent/${module.uuid}`)}
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
              aria-label={module.is_active ? "Arbeitsraum deaktivieren" : "Arbeitsraum aktivieren"}
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
            <IconButton onClick={() => router.push(`/ki-assistent/${module.uuid}`)} title="Arbeitsraum öffnen">
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
                Neuen Link erstellen
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
  onLinksChanged,
}: {
  modules: KiTutorModule[];
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
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
              <th className="text-left pr-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Arbeitsraum</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Quellen</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>Links</th>
              <th className="text-left px-6 pb-3 font-medium text-xs" style={{ color: "var(--muted)" }}>
                <span className="inline-flex items-center gap-1.5">
                  Status
                  <HelpTooltip text="Aktiv: Studierende können sich über Zugangslinks in den Arbeitsraum einschreiben und die Inhalte nutzen. Inaktiv: Der Arbeitsraum ist für Studierende gesperrt. Bestehende Einschreibungen bleiben erhalten." />
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
            onLinksChanged={onLinksChanged}
          />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            Zeige {startIdx + 1} bis {Math.min(startIdx + MODULES_PER_PAGE, modules.length)} von {modules.length} Arbeitsräumen
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
          <h2 className="text-xl font-semibold">Meine Arbeitsräume</h2>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-primary"
          >
            + Neuen Arbeitsraum erstellen
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
          <p className="text-base">Noch keine Arbeitsräume vorhanden.</p>
          <p className="text-sm mt-1">Erstelle deinen ersten Arbeitsraum mit dem Button oben.</p>
        </div>
      ) : (
        <div className="mt-6 md:mt-20">
          <ModuleTable
            modules={modules}
            onToggleActive={handleToggleActive}
            onDelete={handleDelete}
            onLinksChanged={handleLinksChanged}
          />
        </div>
      )}
    </>
  );
}

// ─── Student View ─────────────────────────────────────────────────────────────

function StudentView() {
  const searchParams = useSearchParams();
  const [modules, setModules] = useState<StudentModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrollCode, setEnrollCode] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState<string | null>(null);

  // Auto-fill enrollment code from URL ?code= parameter
  useEffect(() => {
    const code = searchParams.get("code");
    if (code) setEnrollCode(code);
  }, [searchParams]);

  const loadModules = useCallback(async () => {
    try {
      const res = await fetch("/api/ki-assistent/my-modules", { credentials: "include" });
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

  async function handleEnroll(e: React.FormEvent) {
    e.preventDefault();
    if (!enrollCode.trim()) return;
    setEnrolling(true);
    setEnrollError(null);
    try {
      const res = await fetch("/api/ki-assistent/enroll", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enroll_code: enrollCode.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Ungültiger Code");
      }
      setEnrollCode("");
      await loadModules();
    } catch (err: unknown) {
      setEnrollError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setEnrolling(false);
    }
  }

  return (
    <>
      <h1 className="text-3xl font-bold mb-10">Willkommen bei KIS</h1>
      <h2 className="text-xl font-semibold mb-8">Meine Arbeitsräume</h2>

      {/* Enroll form */}
      <section
        className="rounded-xl p-5 mb-8"
        style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
      >
        <p className="text-sm font-medium mb-3" style={{ color: "var(--text)" }}>
          Einschreibecode eingeben
        </p>
        <form onSubmit={handleEnroll} className="flex gap-2">
          <input
            type="text"
            value={enrollCode}
            onChange={(e) => { setEnrollCode(e.target.value); setEnrollError(null); }}
            placeholder="z. B. a1b2c3d4"
            className="flex-1 rounded-lg border px-3 py-2 text-sm focus:outline-none font-mono"
            style={{
              backgroundColor: "var(--bg)",
              borderColor: enrollError ? "#E11D48" : "var(--border)",
              color: "var(--text)",
            }}
          />
          <button
            type="submit"
            disabled={enrolling || !enrollCode.trim()}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 whitespace-nowrap bg-primary"
          >
            {enrolling ? "…" : "Einschreiben"}
          </button>
        </form>
        {enrollError && (
          <p className="mt-2 text-sm" style={{ color: "#E11D48" }}>{enrollError}</p>
        )}
      </section>

      {/* Module list */}
      {loading ? (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Spinner size="lg" />
        </div>
      ) : modules.length === 0 ? (
        <p className="text-center py-10 text-sm" style={{ color: "var(--muted)" }}>
          Du bist noch in keinem Arbeitsraum eingeschrieben.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          {modules.map((m, i) => {
            const href = m.enrollment_id
              ? `/ki-assistent/${m.uuid}?eid=${m.enrollment_id}`
              : `/ki-assistent/${m.uuid}`;
            const untilDate = m.enrolled_until
              ? new Date(m.enrolled_until).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" })
              : null;
            return (
              <li key={`${m.uuid}-${m.enrollment_id ?? i}`} className="px-5 py-4 bg-white hover:bg-gray-50">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium truncate">{m.title}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      {m.description && (
                        <ExpandableText className="text-xs text-gray-400" clampClass="line-clamp-1">{m.description}</ExpandableText>
                      )}
                      {untilDate && (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-400 whitespace-nowrap">
                          <CalendarBlank size={12} />
                          bis {untilDate}
                        </span>
                      )}
                    </div>
                  </div>
                  <Link
                    href={href}
                    className="flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-primary"
                  >
                    Öffnen
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function KiTutorPage() {
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    checkAuthStatus().then((s) => setRole(s.role ?? "lecturer"));
  }, []);

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-5xl mx-auto px-4 pt-10 pb-20 lg:pt-15 lg:pb-30">
        {role !== null && (role === "lecturer" ? <LecturerView /> : <Suspense><StudentView /></Suspense>)}
      </div>
    </ProtectedRoute>
  );
}
