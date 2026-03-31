"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AccessLink {
  id: number;
  code: string;
  expires_at: string;
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

// ─── Help Tooltip ────────────────────────────────────────────────────────────

function HelpTooltip({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex">
      <svg
        className="w-3.5 h-3.5 cursor-help"
        style={{ color: "var(--muted)" }}
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <circle cx="8" cy="8" r="6.5" />
        <path d="M6 6.5a2 2 0 1 1 2.5 1.94V9.5" strokeLinecap="round" />
        <circle cx="8.25" cy="11.5" r="0.5" fill="currentColor" stroke="none" />
      </svg>
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block bg-gray-800 text-white text-xs rounded-lg px-3 py-2 w-64 text-center shadow-lg z-20 leading-relaxed pointer-events-none whitespace-normal break-words">
        {text}
        <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-800" />
      </span>
    </span>
  );
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
    if (!title.trim() || !expiresAt) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("title", title.trim());
      if (description.trim()) form.append("description", description.trim());
      form.append("expires_at", new Date(expiresAt).toISOString());
      const res = await fetch("/api/ki-tutor/modules", {
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
        <h2 className="text-lg font-semibold mb-5" style={{ color: "var(--text)" }}>
          Neues Modul erstellen
        </h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Titel <span style={{ color: "#E11D48" }}>*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none"
              style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
              placeholder="z. B. Einführung in die Informatik"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Beschreibung
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none resize-none"
              style={{ backgroundColor: "var(--bg)", borderColor: "var(--border)", color: "var(--text)" }}
              placeholder="z. B. Sommersemester 2026, Grundlagen der Programmierung"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Einschreibecode gültig bis <span style={{ color: "#E11D48" }}>*</span>
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
              disabled={loading || !title.trim() || !expiresAt}
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
      const res = await fetch(`/api/ki-tutor/modules/${moduleUuid}/access-links`, {
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
        <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--text)" }}>
          Neuen Einschreibelink erstellen
        </h2>
        <p className="text-sm mb-4" style={{ color: "var(--muted)" }}>
          Jeder Link hat eine eigene Laufzeit. Studierende mit unterschiedlichen Links haben getrennte Chat-Verläufe.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Gültig bis <span style={{ color: "#E11D48" }}>*</span>
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

// ─── Link Row (per Access Link) ──────────────────────────────────────────────

function LinkRow({ link, onRequestDelete }: { link: AccessLink; onRequestDelete: (link: AccessLink) => void }) {
  const [copied, setCopied] = useState(false);
  const enrollLink = `${typeof window !== "undefined" ? window.location.origin : ""}/ki-tutor?code=${link.code}`;
  const expiresDate = new Date(link.expires_at).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Berlin",
  });
  const isExpired = new Date(link.expires_at) < new Date();

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(enrollLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  }

  return (
    <div className="group/row flex items-center gap-2 min-w-0 -mx-2 px-2 py-1 rounded-lg hover:bg-gray-100 transition-colors">
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
            <svg className="w-3.5 h-3.5 text-green-600" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 8.5l3.5 3.5 6.5-8" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="5" y="5" width="8" height="8" rx="1.5" />
              <path d="M3 11V3.5A.5.5 0 0 1 3.5 3H11" />
            </svg>
          )}
        </span>
      </button>
      {copied && <span className="text-xs text-green-600 font-medium whitespace-nowrap">Kopiert!</span>}
      {!copied && (
        <span className={`inline-flex items-center gap-1 text-xs whitespace-nowrap ${isExpired ? "text-red-400" : "text-gray-400"}`}>
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="3" width="12" height="11" rx="1.5" />
            <path d="M5 1v3M11 1v3M2 7h12" />
          </svg>
          {isExpired ? "abgelaufen" : `bis ${expiresDate}`}
        </span>
      )}
      <button
        onClick={() => onRequestDelete(link)}
        title="Link löschen"
        className="ml-auto w-7 h-7 flex items-center justify-center rounded-full text-gray-300 opacity-0 group-hover/row:opacity-100 hover:text-primary hover:bg-gray-200 transition-all"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 4h12M5 4V2.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 .5.5V4M6.5 7v5M9.5 7v5M3 4l1 9.5a.5.5 0 0 0 .5.5h7a.5.5 0 0 0 .5-.5L13 4" />
        </svg>
      </button>
    </div>
  );
}

// ─── Module Card (Lecturer) ───────────────────────────────────────────────────

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
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showAddLink, setShowAddLink] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteLinkConfirm, setDeleteLinkConfirm] = useState<AccessLink | null>(null);
  const [deletingLink, setDeletingLink] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const links = module.access_links ?? [];

  // Close overflow menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  async function handleToggle(v: boolean) {
    setToggling(true);
    await onToggleActive(module.uuid, v);
    setToggling(false);
  }

  async function handleDeleteConfirm() {
    setDeleting(true);
    await onDelete(module.uuid);
  }

  async function handleDeleteLinkConfirm() {
    if (!deleteLinkConfirm) return;
    setDeletingLink(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${module.uuid}/access-links/${deleteLinkConfirm.id}`, {
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
      {showAddLink && (
        <AddLinkModal
          moduleUuid={module.uuid}
          onClose={() => setShowAddLink(false)}
          onCreated={handleLinkCreated}
        />
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold text-gray-900 mb-2">Modul löschen?</h3>
            <p className="text-sm text-gray-600 mb-1">
              <span className="font-medium">{module.title}</span>
            </p>
            <p className="text-sm text-red-600 mb-6">
              Das Modul und alle zugehörigen Daten werden unwiderruflich gelöscht.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(false)}
                disabled={deleting}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Abbrechen
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={deleting}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50"
              >
                {deleting ? "..." : "Löschen"}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteLinkConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold text-gray-900 mb-2">Einschreibelink löschen?</h3>
            <p className="text-sm text-gray-600 mb-1">
              <span className="font-medium">...{deleteLinkConfirm.code}</span> – gültig bis {new Date(deleteLinkConfirm.expires_at).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" })}
            </p>
            <p className="text-sm text-red-600 mb-6">
              Der Link wird ungültig. Bereits eingeschriebene Studierende behalten ihren Zugang.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteLinkConfirm(null)}
                disabled={deletingLink}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Abbrechen
              </button>
              <button
                onClick={handleDeleteLinkConfirm}
                disabled={deletingLink}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50"
              >
                {deletingLink ? "..." : "Löschen"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-5 transition-shadow hover:shadow-md">
        {/* Row 1: Header */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <h3 className="text-base font-semibold truncate" style={{ color: "var(--text)" }}>
              {module.title}
            </h3>
            {/* Active pill */}
            <button
              onClick={() => handleToggle(!module.is_active)}
              disabled={toggling}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap disabled:opacity-50 ${
                module.is_active
                  ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${module.is_active ? "bg-emerald-500" : "bg-gray-400"}`} />
              {module.is_active ? "Aktiv" : "Inaktiv"}
            </button>
            <HelpTooltip text="Wenn aktiv, können sich Studierende mit dem Einschreibelink einschreiben und das Modul nutzen. Klicken zum Umschalten." />
            {/* Sources pill */}
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500 whitespace-nowrap">
              <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 3h10v12H3zM6 1v4M10 1v4M6 9h4M6 12h2" />
              </svg>
              {module.source_count} {module.source_count === 1 ? "Quelle" : "Quellen"}
            </span>
          </div>

          {/* Overflow menu */}
          <div className="relative shrink-0" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-primary hover:bg-gray-100 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                <circle cx="8" cy="3" r="1.5" />
                <circle cx="8" cy="8" r="1.5" />
                <circle cx="8" cy="13" r="1.5" />
              </svg>
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-30">
                <button
                  onClick={() => { setMenuOpen(false); setDeleteConfirm(true); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M2 4h12M5 4V2.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 .5.5V4M6.5 7v5M9.5 7v5M3 4l1 9.5a.5.5 0 0 0 .5.5h7a.5.5 0 0 0 .5-.5L13 4" />
                  </svg>
                  Modul löschen
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Row 2: Description */}
        {module.description && (
          <p className="text-sm mt-1.5" style={{ color: "var(--muted)" }}>
            {module.description}
          </p>
        )}

        {/* Row 3: Access Links */}
        <div className="flex flex-col gap-2 mt-3">
          {links.map((link) => (
            <LinkRow key={link.id} link={link} onRequestDelete={setDeleteLinkConfirm} />
          ))}
          <button
            onClick={() => setShowAddLink(true)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-primary transition-colors self-start mt-0.5"
          >
            <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M8 3v10M3 8h10" />
            </svg>
            Neuen Link erstellen
          </button>
        </div>

        {/* Row 4: CTA */}
        <div className="flex justify-end mt-3">
          <Link
            href={`/ki-tutor/${module.uuid}`}
            className="group inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium shrink-0 transition-colors hover:opacity-90 border-2"
            style={{ backgroundColor: "white", color: "var(--kb)", borderColor: "var(--kb)" }}
          >
            Öffnen
            <svg className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 8h10M9 4l4 4-4 4" />
            </svg>
          </Link>
        </div>
      </div>
    </>
  );
}

// ─── Lecturer View ────────────────────────────────────────────────────────────

function LecturerView() {
  const [modules, setModules] = useState<KiTutorModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const loadModules = useCallback(async () => {
    try {
      const res = await fetch("/api/ki-tutor/modules", { credentials: "include" });
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
      const res = await fetch(`/api/ki-tutor/modules/${uuid}`, {
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
      const res = await fetch(`/api/ki-tutor/modules/${uuid}`, {
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

      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-10" style={{ color: "var(--text)" }}>Willkommen bei KIS</h1>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold" style={{ color: "var(--text)" }}>Meine Module</h2>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-primary"
          >
            + Neues Modul erstellen
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
        </div>
      ) : modules.length === 0 ? (
        <div className="text-center py-20" style={{ color: "var(--muted)" }}>
          <p className="text-base">Noch keine Module vorhanden.</p>
          <p className="text-sm mt-1">Erstelle dein erstes Modul mit dem Button oben.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {modules.map((m) => (
            <ModuleCard
              key={m.uuid}
              module={m}
              onToggleActive={handleToggleActive}
              onDelete={handleDelete}
              onLinksChanged={handleLinksChanged}
            />
          ))}
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
      const res = await fetch("/api/ki-tutor/my-modules", { credentials: "include" });
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
      const res = await fetch("/api/ki-tutor/enroll", {
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
      <h1 className="text-3xl font-bold mb-10" style={{ color: "var(--text)" }}>Willkommen bei KIS</h1>
      <h2 className="text-xl font-semibold mb-8" style={{ color: "var(--text)" }}>Meine Module</h2>

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
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent" />
        </div>
      ) : modules.length === 0 ? (
        <p className="text-center py-10 text-sm" style={{ color: "var(--muted)" }}>
          Du bist noch in keinem Modul eingeschrieben.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          {modules.map((m, i) => {
            const href = m.enrollment_id
              ? `/ki-tutor/${m.uuid}?eid=${m.enrollment_id}`
              : `/ki-tutor/${m.uuid}`;
            const untilDate = m.enrolled_until
              ? new Date(m.enrolled_until).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" })
              : null;
            return (
              <li key={`${m.uuid}-${m.enrollment_id ?? i}`} className="px-5 py-4 bg-white hover:bg-gray-50">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-gray-800 truncate">{m.title}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      {m.description && (
                        <p className="text-xs text-gray-400 line-clamp-1">{m.description}</p>
                      )}
                      {untilDate && (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-400 whitespace-nowrap">
                          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="2" y="3" width="12" height="11" rx="1.5" />
                            <path d="M5 1v3M11 1v3M2 7h12" />
                          </svg>
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
