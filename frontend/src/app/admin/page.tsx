"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import { checkAuthStatus } from "@/lib/auth";

type Tab = "pending" | "whitelist" | "users" | "jobs" | "settings" | "apikeys";

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
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {jobs.map((j) => (
                <tr key={j.job_uuid}>
                  <td className="px-4 py-3 text-gray-700 whitespace-nowrap">{j.user_display_name}</td>
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{j.tool_label}</td>
                  <td className="px-4 py-3 text-gray-500 max-w-[200px] truncate">{j.original_filename}</td>
                  <td className="px-4 py-3"><StatusBadge status={j.status} /></td>
                  <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{formatDate(j.created_at)}</td>
                </tr>
              ))}
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
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        setWhitelistEnabled(d.whitelist_enabled ?? true);
        setDemoData(d.demo_data ?? false);
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
    </div>
  );
}

// --- Settings: API-Keys ---
interface ApiConfig {
  deepl_api_key: string;
  elevenlabs_api_key: string;
  kisski_api_key: string;
  kisski_base_url: string;
  kisski_models: { model: string; is_default: number }[];
}

function KeyField({
  label, description, masked, onSave, onDelete,
}: {
  label: string;
  description: string;
  masked: string;
  onSave: (v: string) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!value.trim()) return;
    setSaving(true);
    try {
      await onSave(value.trim());
      setValue("");
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const del = async () => {
    setSaving(true);
    try { await onDelete(); } finally { setSaving(false); }
  };

  return (
    <div className="border border-gray-200 rounded-xl bg-white p-5 space-y-3">
      <div>
        <p className="text-sm font-medium text-gray-800">{label}</p>
        <p className="text-xs text-gray-400 mt-0.5">{description}</p>
      </div>
      {!editing ? (
        <div className="flex items-center gap-3">
          <code className="flex-1 text-sm bg-gray-50 border border-gray-200 rounded-md px-3 py-2 text-gray-600 font-mono">
            {masked || <span className="text-gray-300 italic">Nicht gesetzt</span>}
          </code>
          <button
            onClick={() => setEditing(true)}
            className="px-3 py-1.5 text-xs font-medium text-white bg-[#0066cc] hover:bg-[#0055aa] rounded-md transition-colors"
          >
            {masked ? "Ändern" : "Eintragen"}
          </button>
          {masked && (
            <button
              onClick={del}
              disabled={saving}
              className="px-3 py-1.5 text-xs font-medium text-red-500 border border-red-200 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
            >
              {saving ? "..." : "Entfernen"}
            </button>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <input
            type="password"
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            placeholder="Neuen Key eingeben…"
            className="flex-1 text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc] font-mono"
          />
          <button
            onClick={save}
            disabled={saving || !value.trim()}
            className="px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50 transition-colors"
          >
            {saving ? "..." : "Speichern"}
          </button>
          <button
            onClick={() => { setEditing(false); setValue(""); }}
            className="px-3 py-1.5 text-xs font-medium text-gray-500 border border-gray-300 hover:bg-gray-50 rounded-md transition-colors"
          >
            Abbrechen
          </button>
        </div>
      )}
    </div>
  );
}

function ApiKeysSection() {
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [editingBaseUrl, setEditingBaseUrl] = useState(false);
  const [savingBaseUrl, setSavingBaseUrl] = useState(false);
  const [newModel, setNewModel] = useState("");
  const [addingModel, setAddingModel] = useState(false);

  const load = useCallback(() => {
    fetch("/api/admin/api-config", { credentials: "include" })
      .then((r) => r.json())
      .then((d: ApiConfig) => {
        setConfig(d);
        setBaseUrl(d.kisski_base_url || "https://chat-ai.academiccloud.de/v1");
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  const saveKey = async (keyName: string, value: string) => {
    await fetch(`/api/admin/api-config/keys/${keyName}`, {
      method: "PUT", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });
    load();
  };

  const deleteKey = async (keyName: string) => {
    await fetch(`/api/admin/api-config/keys/${keyName}`, {
      method: "DELETE", credentials: "include",
    });
    load();
  };

  const saveBaseUrl = async () => {
    setSavingBaseUrl(true);
    try {
      await fetch("/api/admin/api-config/kisski-base-url", {
        method: "PUT", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: baseUrl }),
      });
      setEditingBaseUrl(false);
      load();
    } finally {
      setSavingBaseUrl(false);
    }
  };

  const addModel = async () => {
    if (!newModel.trim()) return;
    setAddingModel(true);
    try {
      const isFirst = (config?.kisski_models.length ?? 0) === 0;
      await fetch("/api/admin/api-config/models", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: newModel.trim(), is_default: isFirst }),
      });
      setNewModel("");
      load();
    } finally {
      setAddingModel(false);
    }
  };

  const removeModel = async (model: string) => {
    await fetch(`/api/admin/api-config/models/${encodeURIComponent(model)}`, {
      method: "DELETE", credentials: "include",
    });
    load();
  };

  const setDefault = async (model: string) => {
    await fetch(`/api/admin/api-config/models/${encodeURIComponent(model)}/default`, {
      method: "PATCH", credentials: "include",
    });
    load();
  };

  if (!config) return <Spinner />;

  return (
    <div className="space-y-6">
      {/* API Keys */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">API-Keys (verschlüsselt)</h3>
        <KeyField
          label="DeepL API Key"
          description="Für Übersetzungen (PPTX, DOCX, etc.)"
          masked={config.deepl_api_key}
          onSave={(v) => saveKey("deepl_api_key", v)}
          onDelete={() => deleteKey("deepl_api_key")}
        />
        <KeyField
          label="ElevenLabs API Key"
          description="Für Text-to-Speech und Video-Dubbing"
          masked={config.elevenlabs_api_key}
          onSave={(v) => saveKey("elevenlabs_api_key", v)}
          onDelete={() => deleteKey("elevenlabs_api_key")}
        />
        <KeyField
          label="KISSKI API Key"
          description="Für Skript-Generierung. Kompatibel mit jedem OpenAI-API-Endpunkt: KISSKI/GWDG, Mistral, Together AI, Groq, OpenRouter, Fireworks AI — sowie lokale Modelle über Ollama (Llama, Qwen, Phi, Mistral, Gemma u.a.)."
          masked={config.kisski_api_key}
          onSave={(v) => saveKey("kisski_api_key", v)}
          onDelete={() => deleteKey("kisski_api_key")}
        />
      </div>

      {/* KISSKI Base URL */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">KISSKI Konfiguration</h3>
        <div className="border border-gray-200 rounded-xl bg-white p-5 space-y-3">
          <div>
            <p className="text-sm font-medium text-gray-800">Base URL</p>
            <p className="text-xs text-gray-400 mt-0.5">OpenAI-kompatibler API-Endpunkt</p>
          </div>
          {!editingBaseUrl ? (
            <div className="flex items-center gap-3">
              <code className="flex-1 text-sm bg-gray-50 border border-gray-200 rounded-md px-3 py-2 text-gray-600 font-mono truncate">
                {config.kisski_base_url || "https://chat-ai.academiccloud.de/v1"}
              </code>
              <button
                onClick={() => setEditingBaseUrl(true)}
                className="shrink-0 px-3 py-1.5 text-xs font-medium text-white bg-[#0066cc] hover:bg-[#0055aa] rounded-md transition-colors"
              >
                Ändern
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <input
                type="text"
                autoFocus
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && saveBaseUrl()}
                className="flex-1 text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc]"
              />
              <button
                onClick={saveBaseUrl}
                disabled={savingBaseUrl}
                className="px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50 transition-colors"
              >
                {savingBaseUrl ? "..." : "Speichern"}
              </button>
              <button
                onClick={() => { setEditingBaseUrl(false); setBaseUrl(config.kisski_base_url || "https://chat-ai.academiccloud.de/v1"); }}
                className="px-3 py-1.5 text-xs font-medium text-gray-500 border border-gray-300 hover:bg-gray-50 rounded-md transition-colors"
              >
                Abbrechen
              </button>
            </div>
          )}
        </div>

        {/* KISSKI Models */}
        <div className="border border-gray-200 rounded-xl bg-white p-5 space-y-3">
          <div>
            <p className="text-sm font-medium text-gray-800">Modelle</p>
            <p className="text-xs text-gray-400 mt-0.5">Das Default-Modell wird automatisch verwendet. Weitere Modelle werden später als Dropdown angeboten.</p>
          </div>

          {config.kisski_models.length === 0 ? (
            <p className="text-xs text-gray-400 italic">Noch kein Modell eingetragen</p>
          ) : (
            <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
              {config.kisski_models.map((m) => (
                <li key={m.model} className="px-4 py-2.5 bg-white flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-mono text-gray-700 truncate">{m.model}</span>
                    {m.is_default ? (
                      <span className="text-[10px] font-medium text-white bg-[#0066cc] px-1.5 py-0.5 rounded-full shrink-0">Default</span>
                    ) : (
                      <button
                        onClick={() => setDefault(m.model)}
                        className="text-[10px] text-gray-400 hover:text-[#0066cc] border border-gray-200 hover:border-[#0066cc] px-1.5 py-0.5 rounded-full shrink-0 transition-colors"
                      >
                        Als Default
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => removeModel(m.model)}
                    className="text-xs text-red-400 hover:text-red-600 shrink-0 transition-colors"
                  >
                    Entfernen
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex gap-2">
            <input
              type="text"
              value={newModel}
              onChange={(e) => setNewModel(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addModel()}
              placeholder="z.B. qwen3-30b-a3b-instruct-2507"
              className="flex-1 text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0066cc] font-mono"
            />
            <button
              onClick={addModel}
              disabled={addingModel || !newModel.trim()}
              className="px-3 py-2 text-xs font-medium text-white bg-[#0066cc] hover:bg-[#0055aa] rounded-md disabled:opacity-50 transition-colors"
            >
              {addingModel ? "..." : "Hinzufügen"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ApiKeysTab() {
  return <ApiKeysSection />;
}

function SettingsTab() {
  return <GeneralSettingsSection />;
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
    { key: "apikeys", label: "API-Keys" },
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

        {tab === "apikeys" && <ApiKeysTab />}
        {tab === "pending" && <PendingTab />}
        {tab === "whitelist" && <WhitelistTab adminEmail={adminEmail} />}
        {tab === "users" && <UsersTab />}
        {tab === "jobs" && <JobsTab />}
        {tab === "settings" && <SettingsTab />}
      </main>
    </>
  );
}
