"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import { checkAuthStatus } from "@/lib/auth";

type Tab = "pending" | "whitelist" | "users" | "jobs" | "settings" | "prompts";

interface PendingUser {
  id: number;
  ldap_username: string;
  display_name: string;
  email: string | null;
  created_at: string;
}

interface AdminUser {
  id: number;
  ldap_username: string;
  display_name: string;
  email: string | null;
  active: number;
  created_at: string;
}

interface AdminJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: string;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  user_display_name: string;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + "Z").toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function StatusBadge({ status }: { status: string }) {
  if (status === "success")
    return <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running")
    return <span className="text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  return <span className="text-xs font-medium text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded-full">Wartend</span>;
}

// --- Tab: Pending Users ---
function PendingTab() {
  const [users, setUsers] = useState<PendingUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetch("/api/admin/users/pending", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setUsers(d.users ?? []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async (user: PendingUser) => {
    setApproving(user.id);
    try {
      await fetch(`/api/admin/users/${user.id}/approve`, { method: "POST", credentials: "include" });
      setUsers((prev) => prev.filter((u) => u.id !== user.id));
    } finally {
      setApproving(null);
    }
  };

  if (loading) return <Spinner />;
  if (users.length === 0)
    return <p className="text-sm text-gray-400 text-center py-12">Keine ausstehenden Anfragen</p>;

  return (
    <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden">
      {users.map((u) => (
        <li key={u.id} className="px-5 py-4 bg-white flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-800">{u.display_name}</p>
            <p className="text-xs text-gray-500 mt-0.5">{u.email ?? <span className="text-red-400">Keine Email</span>}</p>
            <p className="text-xs text-gray-400 mt-0.5">Erstellt: {formatDate(u.created_at)}</p>
          </div>
          <button
            onClick={() => approve(u)}
            disabled={!u.email || approving === u.id}
            className="shrink-0 px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-40 transition-colors"
          >
            {approving === u.id ? "..." : "Freischalten"}
          </button>
        </li>
      ))}
    </ul>
  );
}

// --- Tab: Whitelist ---
function WhitelistTab({ adminEmail }: { adminEmail: string }) {
  const [emails, setEmails] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [newEmail, setNewEmail] = useState("");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetch("/api/admin/whitelist", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setEmails(d.emails ?? []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!newEmail.trim()) return;
    setAdding(true);
    setError("");
    try {
      const res = await fetch("/api/admin/whitelist", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: newEmail.trim() }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Fehler beim Hinzufügen");
        return;
      }
      setEmails((prev) => [...prev, newEmail.trim().toLowerCase()]);
      setNewEmail("");
    } finally {
      setAdding(false);
    }
  };

  const remove = async (email: string) => {
    setRemoving(email);
    try {
      const res = await fetch(`/api/admin/whitelist/${encodeURIComponent(email)}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Fehler beim Entfernen");
        return;
      }
      setEmails((prev) => prev.filter((e) => e !== email));
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="name@th-luebeck.de"
          className="flex-1 text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        />
        <button
          onClick={add}
          disabled={adding || !newEmail.trim()}
          className="px-4 py-2 text-sm font-medium text-white bg-[#0066cc] hover:bg-[#0055aa] rounded-md disabled:opacity-40 transition-colors"
        >
          {adding ? "..." : "Hinzufügen"}
        </button>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}

      {loading ? <Spinner /> : emails.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8">Whitelist ist leer</p>
      ) : (
        <ul className="divide-y divide-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          {emails.map((email) => {
            const isAdmin = email.toLowerCase() === adminEmail.toLowerCase();
            return (
              <li key={email} className={`px-5 py-3 flex items-center justify-between gap-4 ${isAdmin ? "bg-gray-50" : "bg-white"}`}>
                <div className="flex items-center gap-2 min-w-0">
                  {isAdmin && (
                    <svg className="w-3.5 h-3.5 text-gray-400 shrink-0" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 1a5 5 0 00-5 5v3H5a2 2 0 00-2 2v10a2 2 0 002 2h14a2 2 0 002-2V11a2 2 0 00-2-2h-2V6a5 5 0 00-5-5zm0 2a3 3 0 013 3v3H9V6a3 3 0 013-3zm0 10a2 2 0 110 4 2 2 0 010-4z" />
                    </svg>
                  )}
                  <span className={`text-sm truncate ${isAdmin ? "text-gray-500" : "text-gray-700"}`}>{email}</span>
                  {isAdmin && (
                    <span className="text-[10px] font-medium text-gray-400 bg-gray-200 px-1.5 py-0.5 rounded-full shrink-0">Admin</span>
                  )}
                </div>
                {isAdmin ? (
                  <span className="text-xs text-gray-300 shrink-0 cursor-default select-none">Entfernen</span>
                ) : (
                  <button
                    onClick={() => remove(email)}
                    disabled={removing === email}
                    className="text-xs text-red-500 hover:underline disabled:opacity-50 shrink-0"
                  >
                    {removing === email ? "..." : "Entfernen"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// --- Tab: All Users ---
function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 350);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => { setOffset(0); }, [debouncedQ, limit, dateFrom, dateTo]);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      q: debouncedQ,
    });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    fetch(`/api/admin/users?${params}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => { setUsers(d.users ?? []); setTotal(d.total ?? 0); })
      .finally(() => setLoading(false));
  }, [limit, offset, debouncedQ, dateFrom, dateTo]);

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Suche: Name, Username, Email..."
          className="flex-1 min-w-[200px] text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title="Von"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title="Bis"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        />
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        >
          <option value={50}>50 pro Seite</option>
          <option value={100}>100 pro Seite</option>
        </select>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {total} User
        </span>
      </div>

      {loading ? <Spinner /> : users.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-12">Keine User gefunden</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Erstellt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-800">{u.display_name}</p>
                    <p className="text-xs text-gray-400">{u.ldap_username}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{u.email ?? <span className="text-gray-300">—</span>}</td>
                  <td className="px-4 py-3">
                    {u.active ? (
                      <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Aktiv</span>
                    ) : (
                      <span className="text-xs font-medium text-red-600 bg-red-50 px-2 py-0.5 rounded-full">Inaktiv</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{formatDate(u.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={currentPage === 1}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-50"
          >
            ‹
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            let start = Math.max(1, currentPage - 3);
            const end = Math.min(totalPages, start + 6);
            start = Math.max(1, end - 6);
            const page = start + i;
            if (page > totalPages) return null;
            return (
              <button
                key={page}
                onClick={() => setOffset((page - 1) * limit)}
                className={`px-3 py-1.5 text-sm border rounded-md ${
                  page === currentPage
                    ? "bg-[#0066cc] text-white border-[#0066cc]"
                    : "border-gray-300 hover:bg-gray-50"
                }`}
              >
                {page}
              </button>
            );
          })}
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-50"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

// --- Tab: All Jobs ---
function JobsTab() {
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [cancelling, setCancelling] = useState<string | null>(null);

  const handleCancel = async (jobUuid: string) => {
    if (!confirm("Job abbrechen und löschen?")) return;
    setCancelling(jobUuid);
    try {
      await fetch(`/api/admin/jobs/${jobUuid}`, { method: "DELETE", credentials: "include" });
      setJobs((prev) => prev.filter((j) => j.job_uuid !== jobUuid));
      setTotal((t) => t - 1);
      window.dispatchEvent(new Event("kis-jobs-changed"));
    } finally {
      setCancelling(null);
    }
  };

  // Debounce search input 350ms
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 350);
    return () => clearTimeout(t);
  }, [q]);

  // Reset to page 1 when search, limit, or dates change
  useEffect(() => { setOffset(0); }, [debouncedQ, limit, dateFrom, dateTo]);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      q: debouncedQ,
    });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    fetch(`/api/admin/jobs?${params}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => { setJobs(d.jobs ?? []); setTotal(d.total ?? 0); })
      .finally(() => setLoading(false));
  }, [limit, offset, debouncedQ, dateFrom, dateTo]);

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Suche: User, Tool, Datei..."
          className="flex-1 min-w-[200px] text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title="Von"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title="Bis"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        />
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
        >
          <option value={50}>50 pro Seite</option>
          <option value={100}>100 pro Seite</option>
        </select>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {total} Ergebnis{total !== 1 ? "se" : ""}
        </span>
      </div>

      {/* Table */}
      {loading ? <Spinner /> : jobs.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-12">Keine Jobs gefunden</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3 text-left">User</th>
                <th className="px-4 py-3 text-left">Tool</th>
                <th className="px-4 py-3 text-left">Datei</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Erstellt</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {jobs.map((j) => {
                const isActive = j.status === "pending" || j.status === "running";
                return (
                  <tr key={j.job_uuid}>
                    <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{j.user_display_name}</td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{j.tool_label}</td>
                    <td className="px-4 py-3 text-gray-500 max-w-[200px] truncate">{j.original_filename}</td>
                    <td className="px-4 py-3"><StatusBadge status={j.status} /></td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{formatDate(j.created_at)}</td>
                    <td className="px-4 py-3">
                      {isActive && (
                        <button
                          onClick={() => handleCancel(j.job_uuid)}
                          disabled={cancelling === j.job_uuid}
                          className="text-xs text-red-500 hover:underline disabled:opacity-40"
                        >
                          {cancelling === j.job_uuid ? "..." : "Abbrechen"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={currentPage === 1}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-50"
          >
            ‹
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            // Sliding window of up to 7 pages centered around current page
            const half = 3;
            let start = Math.max(1, currentPage - half);
            const end = Math.min(totalPages, start + 6);
            start = Math.max(1, end - 6);
            const page = start + i;
            if (page > totalPages) return null;
            return (
              <button
                key={page}
                onClick={() => setOffset((page - 1) * limit)}
                className={`px-3 py-1.5 text-sm border rounded-md ${
                  page === currentPage
                    ? "bg-[#0066cc] text-white border-[#0066cc]"
                    : "border-gray-300 hover:bg-gray-50"
                }`}
              >
                {page}
              </button>
            );
          })}
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-50"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

// --- Settings: General toggles ---
function GeneralSettingsSection() {
  const [whitelistEnabled, setWhitelistEnabled] = useState<boolean | null>(null);
  const [demoData, setDemoData] = useState<boolean | null>(null);
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState<boolean>(true);
  const [elevenlabsConfigured, setElevenlabsConfigured] = useState<boolean>(false);
  const [kokoroEnabled, setKokoroEnabled] = useState<boolean>(false);
  const [kokoroConfigured, setKokoroConfigured] = useState<boolean>(false);
  const [kokoroAvailable, setKokoroAvailable] = useState<boolean>(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        setWhitelistEnabled(d.whitelist_enabled ?? true);
        setDemoData(d.demo_data ?? false);
        setElevenlabsEnabled(d.elevenlabs_enabled ?? true);
        setElevenlabsConfigured(d.elevenlabs_configured ?? false);
        setKokoroEnabled(d.kokoro_enabled ?? true);
        setKokoroConfigured(d.kokoro_configured ?? false);
        setKokoroAvailable(d.kokoro_available ?? false);
      });
  }, []);

  const patch = async (body: Record<string, boolean>) => {
    setSaving(true);
    try {
      await fetch("/api/admin/settings", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } finally {
      setSaving(false);
    }
  };

  if (whitelistEnabled === null || demoData === null) return <Spinner />;

  return (
    <div className="space-y-4">
      {/* Whitelist */}
      <div className="border border-gray-200 rounded-xl bg-white p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-800">Whitelist-Modus</p>
            <p className="text-xs text-gray-500 mt-1">
              {whitelistEnabled
                ? "Aktiv — nur freigeschaltete E-Mail-Adressen dürfen sich einloggen."
                : "Deaktiviert — alle authentifizierten TH-Accounts haben Zugang."}
            </p>
          </div>
          <button
            onClick={() => { const v = !whitelistEnabled; setWhitelistEnabled(v); patch({ whitelist_enabled: v }); }}
            disabled={saving}
            className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
              whitelistEnabled ? "bg-[#0066cc]" : "bg-gray-300"
            } disabled:opacity-50`}
            aria-label="Whitelist umschalten"
          >
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              whitelistEnabled ? "translate-x-5" : "translate-x-0"
            }`} />
          </button>
        </div>
        {!whitelistEnabled && (
          <p className="mt-3 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
            Achtung: Alle TH-Mitarbeiter mit gültigem LDAP-Account können sich einloggen.
          </p>
        )}
      </div>

      {/* Demo-Modus */}
      <div className="border border-gray-200 rounded-xl bg-white p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-800">Demo-Modus</p>
            <p className="text-xs text-gray-500 mt-1">
              {demoData
                ? "Aktiv — Demo-Screencast mit vorgefertigten Daten ist sichtbar."
                : "Deaktiviert — Demo-Screencast ist ausgeblendet."}
            </p>
          </div>
          <button
            onClick={() => { const v = !demoData; setDemoData(v); patch({ demo_data: v }); }}
            disabled={saving}
            className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
              demoData ? "bg-[#0066cc]" : "bg-gray-300"
            } disabled:opacity-50`}
            aria-label="Demo-Modus umschalten"
          >
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              demoData ? "translate-x-5" : "translate-x-0"
            }`} />
          </button>
        </div>
        {demoData && (
          <p className="mt-3 text-xs text-blue-600 bg-blue-50 border border-blue-200 rounded-md px-3 py-2">
            Demo-Screencast ist für alle eingeloggten User sichtbar.
          </p>
        )}
      </div>

      {/* TTS-Anbieter */}
      <div className="border border-gray-200 rounded-xl bg-white p-5">
        <p className="text-sm font-medium text-gray-800 mb-4">TTS-Anbieter</p>
        <div className="space-y-4">
          {/* ElevenLabs */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm text-gray-700">ElevenLabs</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {elevenlabsEnabled
                  ? "Aktiv — als Anbieter wählbar."
                  : "Deaktiviert — wird nicht angezeigt."}
              </p>
              {!elevenlabsConfigured && (
                <p className="mt-1 text-xs text-gray-400">
                  <code className="font-mono">ELEVENLABS_API_KEY</code> nicht gesetzt
                </p>
              )}
            </div>
            <button
              onClick={() => { const v = !elevenlabsEnabled; setElevenlabsEnabled(v); patch({ elevenlabs_enabled: v }); }}
              disabled={saving || !elevenlabsConfigured}
              title={!elevenlabsConfigured ? "ELEVENLABS_API_KEY ist nicht in .env gesetzt" : undefined}
              className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
                elevenlabsEnabled ? "bg-[#0066cc]" : "bg-gray-300"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
              aria-label="ElevenLabs umschalten"
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                elevenlabsEnabled ? "translate-x-5" : "translate-x-0"
              }`} />
            </button>
          </div>

          <div className="border-t border-gray-100" />

          {/* Kokoro */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm text-gray-700">Kokoro TTS</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {!kokoroEnabled
                  ? "Deaktiviert — wird nicht angezeigt."
                  : kokoroAvailable
                    ? "Aktiv — als Anbieter wählbar."
                    : "Aktiviert — Server nicht erreichbar."}
              </p>
              {!kokoroConfigured && (
                <p className="mt-1 text-xs text-gray-400">
                  <code className="font-mono">KOKORO_BASE_URL</code> nicht gesetzt
                </p>
              )}
            </div>
            <button
              onClick={() => { const v = !kokoroEnabled; setKokoroEnabled(v); patch({ kokoro_enabled: v }); }}
              disabled={saving || !kokoroConfigured}
              title={!kokoroConfigured ? "KOKORO_BASE_URL ist nicht in .env gesetzt" : undefined}
              className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
                kokoroEnabled ? "bg-[#0066cc]" : "bg-gray-300"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
              aria-label="Kokoro TTS umschalten"
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                kokoroEnabled ? "translate-x-5" : "translate-x-0"
              }`} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Settings: Tool visibility ---
interface ToolEntry {
  key: string;
  label: string;
  enabled: boolean;
}

function ToolsSettingsSection() {
  const [tools, setTools] = useState<ToolEntry[] | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setTools(d.tools ?? []));
  }, []);

  const toggle = async (key: string, enabled: boolean) => {
    setSaving(key);
    setTools((prev) => prev?.map((t) => (t.key === key ? { ...t, enabled } : t)) ?? null);
    try {
      await fetch(`/api/admin/tools/${key}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
    } finally {
      setSaving(null);
    }
  };

  if (!tools) return <Spinner />;

  return (
    <div className="border border-gray-200 rounded-xl bg-white p-5">
      <p className="text-sm font-medium text-gray-800 mb-1">Tools ein-/ausschalten</p>
      <p className="text-xs text-gray-500 mb-4">Deaktivierte Tools werden auf der Startseite ausgeblendet.</p>
      <div className="space-y-3">
        {tools.map((tool) => (
          <div key={tool.key} className="flex items-center justify-between">
            <span className="text-sm text-gray-700">{tool.label}</span>
            <button
              onClick={() => toggle(tool.key, !tool.enabled)}
              disabled={saving === tool.key}
              className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
                tool.enabled ? "bg-[#0066cc]" : "bg-gray-300"
              } disabled:opacity-50`}
              aria-label={`${tool.label} ${tool.enabled ? "deaktivieren" : "aktivieren"}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                tool.enabled ? "translate-x-5" : "translate-x-0"
              }`} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Tab: System Prompts ---

interface AdminPrompt {
  key: string;
  label: string;
  description: string;
  editable: boolean;
  current_value: string;
  default_value: string;
}

function PromptsTab() {
  const [prompts, setPrompts] = useState<AdminPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await fetch("/api/admin/prompts", { credentials: "include" });
    const d = await r.json();
    const ps: AdminPrompt[] = d.prompts ?? [];
    setPrompts(ps);
    const initial: Record<string, string> = {};
    for (const p of ps) initial[p.key] = p.current_value;
    setValues(initial);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (key: string) => {
    setSaving(key);
    try {
      await fetch(`/api/admin/prompts/${key}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: values[key] }),
      });
      setSaved(key);
      setTimeout(() => setSaved(null), 2000);
    } finally {
      setSaving(null);
    }
  };

  const reset = async (key: string, defaultValue: string) => {
    setSaving(key);
    try {
      await fetch(`/api/admin/prompts/${key}/reset`, { method: "DELETE", credentials: "include" });
      setValues((v) => ({ ...v, [key]: defaultValue }));
      setSaved(key);
      setTimeout(() => setSaved(null), 2000);
    } finally {
      setSaving(null);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-5">
      {prompts.map((p) => (
        <div
          key={p.key}
          className={`rounded-xl border p-5 space-y-3 ${p.editable ? "border-gray-200 bg-white" : "border-gray-100 bg-gray-50"}`}
        >
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-gray-800">{p.label}</p>
                {!p.editable && (
                  <span className="inline-flex items-center gap-1 text-xs text-gray-400 bg-gray-200 px-2 py-0.5 rounded-full">
                    <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M12 6h-1V4a3 3 0 0 0-6 0v2H4a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1zm-5 5.73V13h2v-1.27a1.5 1.5 0 1 0-2 0zM7 4a1 1 0 0 1 2 0v2H7V4z" />
                    </svg>
                    Schreibgeschützt
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-0.5">{p.description}</p>
            </div>
          </div>
          <textarea
            value={p.editable ? (values[p.key] ?? p.current_value) : p.current_value}
            onChange={p.editable ? (e) => setValues((v) => ({ ...v, [p.key]: e.target.value })) : undefined}
            readOnly={!p.editable}
            rows={14}
            spellCheck={false}
            className={`w-full text-xs font-mono rounded-lg border px-3 py-2.5 resize-y leading-relaxed focus:outline-none ${
              p.editable
                ? "border-gray-300 bg-white text-gray-800 focus:ring-2 focus:ring-[#0066cc]"
                : "border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed select-none"
            }`}
          />
          {p.editable && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => save(p.key)}
                disabled={saving === p.key}
                className="text-sm bg-[#0066cc] text-white px-4 py-1.5 rounded-lg hover:bg-[#0055aa] disabled:opacity-50"
              >
                {saving === p.key ? "Speichert..." : saved === p.key ? "Gespeichert ✓" : "Speichern"}
              </button>
              <button
                onClick={() => reset(p.key, p.default_value)}
                disabled={saving === p.key || values[p.key] === p.default_value}
                className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40"
              >
                Zurücksetzen
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function SettingsTab() {
  return (
    <div className="space-y-6">
      <GeneralSettingsSection />
      <ToolsSettingsSection />
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("settings");
  const [checking, setChecking] = useState(true);
  const [adminEmail, setAdminEmail] = useState("");
  const router = useRouter();

  useEffect(() => {
    checkAuthStatus().then((s) => {
      if (!s.authenticated) { router.push("/login"); return; }
      if (!s.is_admin) { router.push("/"); return; }
      setAdminEmail(s.email ?? "");
      setChecking(false);
    });
  }, [router]);

  if (checking) return null;

  const tabs: { key: Tab; label: string }[] = [
    { key: "settings", label: "Einstellungen" },
    { key: "prompts", label: "Prompts" },
    { key: "pending", label: "Ausstehend" },
    { key: "whitelist", label: "Whitelist" },
    { key: "users", label: "Alle User" },
    { key: "jobs", label: "Alle Jobs" },
  ];

  return (
    <>
      <Header showLogout />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-6">Admin-Bereich</h2>

        <div className="flex gap-1 border-b border-gray-200 mb-6 overflow-x-auto scrollbar-none">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0 ${
                tab === t.key
                  ? "border-[#0066cc] text-[#0066cc]"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "pending" && <PendingTab />}
        {tab === "whitelist" && <WhitelistTab adminEmail={adminEmail} />}
        {tab === "users" && <UsersTab />}
        {tab === "jobs" && <JobsTab />}
        {tab === "settings" && <SettingsTab />}
        {tab === "prompts" && <PromptsTab />}
      </main>
    </>
  );
}
