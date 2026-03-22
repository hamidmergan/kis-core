"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import BackLink from "@/components/BackLink";
import { checkAuthStatus } from "@/lib/auth";

// ─── Types ────────────────────────────────────────────────────────────────────

interface KiTutorModule {
  uuid: string;
  title: string;
  description?: string | null;
  status: "pending" | "indexing" | "ready" | "failed";
  source_count: number;
  is_active: boolean;
  enroll_code: string | null;
  enroll_code_expires: string | null;
  created_at: string | null;
}

interface StudentModule {
  uuid: string;
  title: string;
  description?: string | null;
  status: string;
  created_at: string | null;
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; bg: string; color: string }> = {
  pending:  { label: "Ausstehend",      bg: "#F1F5F9", color: "#64748B" },
  indexing: { label: "Wird indiziert",  bg: "#FEF9C3", color: "#A16207" },
  ready:    { label: "Bereit",          bg: "#DCFCE7", color: "#166534" },
  failed:   { label: "Fehler",          bg: "#FEE2E2", color: "#991B1B" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, bg: "#F1F5F9", color: "#64748B" };
  return (
    <span
      className="text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap"
      style={{ backgroundColor: cfg.bg, color: cfg.color }}
    >
      {cfg.label}
    </span>
  );
}

// ─── Toggle ───────────────────────────────────────────────────────────────────

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
      style={{ backgroundColor: checked ? "#004261" : "#CBD5E1" }}
    >
      <span
        className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
        style={{ transform: checked ? "translateX(16px)" : "translateX(0)" }}
      />
    </button>
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
              placeholder="Optional"
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
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: "#004261" }}
            >
              {loading ? "Erstellen…" : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Renew Code Modal ─────────────────────────────────────────────────────────

function RenewCodeModal({
  moduleUuid,
  onClose,
  onRenewed,
}: {
  moduleUuid: string;
  onClose: () => void;
  onRenewed: (code: string, expires: string) => void;
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
      const res = await fetch(`/api/ki-tutor/modules/${moduleUuid}/renew-code`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expires_at: new Date(expiresAt).toISOString() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Fehler beim Erneuern");
      }
      const data = await res.json();
      onRenewed(data.enroll_code, data.enroll_code_expires);
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
        <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text)" }}>
          Code erneuern
        </h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text)" }}>
              Neues Ablaufdatum <span style={{ color: "#E11D48" }}>*</span>
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
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: "#004261" }}
            >
              {loading ? "Erneuern…" : "Erneuern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Module Card (Lecturer) ───────────────────────────────────────────────────

function ModuleCard({
  module,
  onToggleActive,
  onDelete,
  onRenewed,
}: {
  module: KiTutorModule;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onRenewed: (uuid: string, code: string, expires: string) => void;
}) {
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showRenew, setShowRenew] = useState(false);

  const expiresDate = module.enroll_code_expires
    ? new Date(module.enroll_code_expires).toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : null;

  async function handleToggle(v: boolean) {
    setToggling(true);
    await onToggleActive(module.uuid, v);
    setToggling(false);
  }

  async function handleDelete() {
    if (!confirm(`Modul "${module.title}" wirklich löschen?`)) return;
    setDeleting(true);
    await onDelete(module.uuid);
  }

  return (
    <>
      {showRenew && (
        <RenewCodeModal
          moduleUuid={module.uuid}
          onClose={() => setShowRenew(false)}
          onRenewed={(code, expires) => {
            onRenewed(module.uuid, code, expires);
          }}
        />
      )}
      <div
        className="rounded-xl p-5 flex flex-col gap-3"
        style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
      >
        {/* Header */}
        <div className="flex items-start gap-3 justify-between">
          <div className="min-w-0">
            <h3 className="font-semibold text-base truncate" style={{ color: "var(--text)" }}>
              {module.title}
            </h3>
            {module.description && (
              <p className="text-sm mt-0.5 line-clamp-2" style={{ color: "var(--muted)" }}>
                {module.description}
              </p>
            )}
          </div>
          <StatusBadge status={module.status} />
        </div>

        {/* Meta */}
        <div className="flex items-center gap-4 text-sm" style={{ color: "var(--muted)" }}>
          <span>{module.source_count} {module.source_count === 1 ? "Source" : "Sources"}</span>
          <div className="flex items-center gap-2">
            <span>Aktiv</span>
            <Toggle checked={module.is_active} onChange={handleToggle} disabled={toggling} />
          </div>
        </div>

        {/* Enroll code */}
        {module.enroll_code && (
          <div
            className="rounded-lg px-3 py-2 flex items-center gap-2 text-sm"
            style={{ backgroundColor: "var(--bg)", border: "1px solid var(--border)" }}
          >
            <span style={{ color: "var(--muted)" }}>Code:</span>
            <code className="font-mono font-semibold tracking-wider" style={{ color: "var(--text)" }}>
              {module.enroll_code}
            </code>
            {expiresDate && (
              <span className="ml-auto text-xs" style={{ color: "var(--muted)" }}>
                bis {expiresDate}
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-2 pt-1">
          <Link
            href={`/ki-tutor/${module.uuid}`}
            className="px-3 py-1.5 rounded-lg text-sm font-medium text-white"
            style={{ backgroundColor: "#004261" }}
          >
            Öffnen
          </Link>
          <button
            type="button"
            onClick={() => setShowRenew(true)}
            className="px-3 py-1.5 rounded-lg text-sm font-medium"
            style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
          >
            Code erneuern
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="px-3 py-1.5 rounded-lg text-sm font-medium ml-auto disabled:opacity-50"
            style={{ backgroundColor: "#FEE2E2", color: "#991B1B" }}
          >
            {deleting ? "Löschen…" : "Löschen"}
          </button>
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

  function handleRenewed(uuid: string, code: string, expires: string) {
    setModules((prev) =>
      prev.map((m) => m.uuid === uuid ? { ...m, enroll_code: code, enroll_code_expires: expires } : m)
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
        <BackLink />
        <div className="flex items-center justify-between mt-2">
          <h1 className="text-3xl font-bold" style={{ color: "var(--text)" }}>KI Tutor</h1>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white"
            style={{ backgroundColor: "#004261" }}
          >
            + Neues Modul erstellen
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: "#004261" }} />
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
              onRenewed={handleRenewed}
            />
          ))}
        </div>
      )}
    </>
  );
}

// ─── Student View ─────────────────────────────────────────────────────────────

function StudentView() {
  const [modules, setModules] = useState<StudentModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrollCode, setEnrollCode] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState<string | null>(null);

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
      <h1 className="text-3xl font-bold mb-8" style={{ color: "var(--text)" }}>Meine Module</h1>

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
            className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 whitespace-nowrap"
            style={{ backgroundColor: "#004261" }}
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
          <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: "#004261" }} />
        </div>
      ) : modules.length === 0 ? (
        <p className="text-center py-10 text-sm" style={{ color: "var(--muted)" }}>
          Du bist noch in keinem Modul eingeschrieben.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {modules.map((m) => (
            <div
              key={m.uuid}
              className="rounded-xl p-5 flex items-center justify-between gap-4"
              style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <h3 className="font-semibold text-base truncate" style={{ color: "var(--text)" }}>
                    {m.title}
                  </h3>
                  <StatusBadge status={m.status} />
                </div>
                {m.description && (
                  <p className="text-sm line-clamp-2" style={{ color: "var(--muted)" }}>
                    {m.description}
                  </p>
                )}
              </div>
              <Link
                href={`/ki-tutor/${m.uuid}`}
                className="flex-shrink-0 px-3 py-1.5 rounded-lg text-sm font-medium text-white"
                style={{ backgroundColor: "#004261" }}
              >
                Öffnen
              </Link>
            </div>
          ))}
        </div>
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
        {role !== null && (role === "lecturer" ? <LecturerView /> : <StudentView />)}
      </div>
    </ProtectedRoute>
  );
}
