"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import { checkAuthStatus } from "@/lib/auth";
import Spinner from "@/components/Spinner";

type Tab = "pending" | "whitelist" | "users" | "jobs" | "stats" | "ki-tutor" | "settings" | "prompts" | "quota";

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
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin",
  });
}

function StatusBadge({ status }: { status: string }) {
  if (status === "success")
    return <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">Fertig</span>;
  if (status === "failed")
    return <span className="text-xs font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded-full">Fehler</span>;
  if (status === "running")
    return <span className="text-xs font-medium text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full animate-pulse">Läuft</span>;
  if (status === "queued")
    return <span className="text-xs font-medium text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">In der Schlange</span>;
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

  if (loading) return <Spinner className="flex justify-center py-12" />;
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
          className="flex-1 text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          onClick={add}
          disabled={adding || !newEmail.trim()}
          className="px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary-hover rounded-md disabled:opacity-40 transition-colors"
        >
          {adding ? "..." : "Hinzufügen"}
        </button>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}

      {loading ? <Spinner className="flex justify-center py-12" /> : emails.length === 0 ? (
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
function UsersTab({ onOpenQuota }: { onOpenQuota: (userId: number) => void }) {
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
          className="flex-1 min-w-[200px] text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title="Von"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title="Bis"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value={50}>50 pro Seite</option>
          <option value={100}>100 pro Seite</option>
        </select>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {total} User
        </span>
      </div>

      {loading ? <Spinner className="flex justify-center py-12" /> : users.length === 0 ? (
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
                <th className="px-4 py-3 text-left">Kontingente</th>
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
                  <td className="px-4 py-3">
                    <button onClick={() => onOpenQuota(u.id)} className="text-xs text-primary hover:underline whitespace-nowrap">
                      Details
                    </button>
                  </td>
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
                    ? "bg-primary text-white border-primary"
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

// --- Tab: Statistiken ---
interface ToolStat {
  tool: string;
  label: string;
  total: number;
  success: number;
  failed: number;
  avg_seconds: number | null;
}
interface ActivityEntry {
  user: string;
  tool: string;
  tool_label: string;
  status: string;
  filename: string | null;
  created_at: string;
  duration_seconds: number | null;
}
interface StatsData {
  by_tool: ToolStat[];
  activity: ActivityEntry[];
  days: number;
}

function StatsTab() {
  const [data, setData] = useState<StatsData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/admin/stats?days=${days}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setData(d))
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return <p className="text-sm text-gray-500">Laden…</p>;
  if (!data) return <p className="text-sm text-red-500">Fehler beim Laden</p>;

  const totalJobs = data.by_tool.reduce((s, t) => s + t.total, 0);
  const totalSuccess = data.by_tool.reduce((s, t) => s + t.success, 0);
  const totalFailed = data.by_tool.reduce((s, t) => s + t.failed, 0);

  return (
    <div className="space-y-6">
      {/* Zeitraum-Auswahl */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">Zeitraum:</span>
        {[7, 30, 90, 180].map((d) => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1 text-xs rounded-full border transition-colors ${days === d ? "bg-primary text-white border-primary" : "border-gray-300 text-gray-600 hover:border-gray-400"}`}>
            {d === 7 ? "7 Tage" : d === 30 ? "1 Monat" : d === 90 ? "3 Monate" : "6 Monate"}
          </button>
        ))}
      </div>

      {/* Übersicht-Karten */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Gesamt</p>
          <p className="text-2xl font-bold text-gray-800 mt-1">{totalJobs}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Erfolgreich</p>
          <p className="text-2xl font-bold text-green-600 mt-1">{totalSuccess}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Fehlgeschlagen</p>
          <p className="text-2xl font-bold text-red-600 mt-1">{totalFailed}</p>
        </div>
      </div>

      {/* Jobs pro Tool */}
      {data.by_tool.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {data.by_tool.map((t) => (
            <div key={t.tool} className="bg-white border border-gray-200 rounded-lg p-4">
              <p className="text-xs font-medium text-gray-500 truncate">{t.label}</p>
              <p className="text-xl font-bold text-gray-800 mt-1">{t.total}</p>
              <div className="flex items-center gap-3 mt-2 text-xs">
                <span className="text-green-600">{t.success} ok</span>
                {t.failed > 0 && <span className="text-red-600">{t.failed} fehl</span>}
              </div>
              <p className="text-[10px] text-gray-400 mt-1">
                {t.avg_seconds != null
                  ? t.avg_seconds >= 60
                    ? `Ø ${Math.round(t.avg_seconds / 60)} min`
                    : `Ø ${Math.round(t.avg_seconds)} s`
                  : ""}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Aktivitätslog */}
      {data.activity.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <h3 className="text-sm font-medium text-gray-700 p-4 pb-2">Letzte Aktivität</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs text-gray-500 uppercase">
                  <th className="px-4 py-2">User</th>
                  <th className="px-4 py-2">Tool</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2 text-right">Dauer</th>
                  <th className="px-4 py-2 text-right">Datum</th>
                </tr>
              </thead>
              <tbody>
                {data.activity.map((a, i) => (
                  <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-700">{a.user}</td>
                    <td className="px-4 py-2 text-gray-600">{a.tool_label}</td>
                    <td className="px-4 py-2"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-2 text-right text-gray-500">
                      {a.duration_seconds != null
                        ? a.duration_seconds >= 60
                          ? `${Math.round(a.duration_seconds / 60)} min`
                          : `${Math.round(a.duration_seconds)} s`
                        : "–"}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-400 whitespace-nowrap">{formatDate(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Tab: KI-Tutor ---
interface KiTutorSummary {
  total_modules: number;
  active_students: number;
  total_answers: number;
  total_chat_messages: number;
}
interface KiTutorStudentStat {
  name: string;
  answers: number;
  correct: number;
  accuracy: number;
  lerntools: number;
  sprachtraining: number;
  chat_messages: number;
}
interface KiTutorModuleStat {
  module_uuid: string;
  title: string;
  owner: string;
  is_active: boolean;
  source_count: number;
  enrollment_count: number;
  total_answers: number;
  accuracy: number;
  chat_messages: number;
  dozent: { messages: number; exercises: number };
  students: KiTutorStudentStat[];
}
interface KiTutorStatsData {
  summary: KiTutorSummary;
  module_stats: KiTutorModuleStat[];
  days: number;
}

type StatsMode = "quelle" | "glossar";
const MODE_META: Record<StatsMode, { label: string; accent: string }> = {
  quelle:  { label: "Lerntools",       accent: "var(--kb)" },
  glossar: { label: "Fachsprachentraining",  accent: "var(--st)" },
};

function KiTutorTab() {
  const [data, setData] = useState<KiTutorStatsData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<StatsMode>("quelle");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    setLoading(true);
    fetch(`/api/admin/ki-tutor/stats?days=${days}&mode=${mode}`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setData(d))
      .finally(() => setLoading(false));
  }, [days, mode]);

  const toggle = (uuid: string) => setExpanded((prev) => {
    const next = new Set(prev);
    next.has(uuid) ? next.delete(uuid) : next.add(uuid);
    return next;
  });

  if (loading && !data) return <p className="text-sm text-gray-500">Laden…</p>;
  if (!data) return <p className="text-sm text-red-500">Fehler beim Laden</p>;

  const accent = MODE_META[mode].accent;

  return (
    <div className={`space-y-6 transition-opacity ${loading ? "opacity-50 pointer-events-none" : ""}`}>
      {/* Mode + Zeitraum */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1">
          {(["quelle", "glossar"] as StatsMode[]).map((m) => {
            const active = mode === m;
            const meta = MODE_META[m];
            return (
              <button key={m} onClick={() => setMode(m)}
                className="px-4 py-1.5 text-xs font-medium rounded-full border transition-colors"
                style={active
                  ? { backgroundColor: meta.accent, color: "#fff", borderColor: meta.accent }
                  : { borderColor: "#d1d5db", color: "#6b7280" }}>
                {meta.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90, 180].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${days === d ? "bg-primary text-white border-primary" : "border-gray-300 text-gray-600 hover:border-gray-400"}`}>
              {d === 7 ? "7 Tage" : d === 30 ? "1 Monat" : d === 90 ? "3 Monate" : "6 Monate"}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Module</p>
          <p className="text-2xl font-bold text-gray-800 mt-1">{data.summary.total_modules}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Aktive Teilnehmer ({days}T)</p>
          <p className="text-2xl font-bold text-gray-800 mt-1">{data.summary.active_students}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Übungen ({days}T)</p>
          <p className="text-2xl font-bold mt-1" style={{ color: accent }}>{data.summary.total_answers.toLocaleString("de-DE")}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Chat ({days}T)</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--st)" }}>{data.summary.total_chat_messages.toLocaleString("de-DE")}</p>
        </div>
      </div>

      {/* Module-Tabelle */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs text-gray-500 uppercase">
                <th className="px-4 py-2 w-6"></th>
                <th className="px-4 py-2">Modul</th>
                <th className="px-4 py-2">Ersteller</th>
                <th className="px-4 py-2 text-right">Quellen</th>
                <th className="px-4 py-2 text-right">Teilnehmer</th>
                <th className="px-4 py-2 text-right">Übungen</th>
                <th className="px-4 py-2 text-right">Chat</th>
              </tr>
            </thead>
            <tbody>
              {data.module_stats.map((m) => {
                const isOpen = expanded.has(m.module_uuid);
                return (
                  <React.Fragment key={m.module_uuid}>
                    <tr onClick={() => toggle(m.module_uuid)}
                        className={`border-b border-gray-50 cursor-pointer transition-colors ${isOpen ? "bg-gray-50" : "hover:bg-gray-50"}`}>
                      <td className="px-4 py-2 text-gray-400 text-xs">{isOpen ? "▼" : "▶"}</td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full shrink-0 ${m.is_active ? "bg-green-400" : "bg-gray-300"}`} />
                          <span className="font-medium text-gray-700 truncate max-w-[200px]">{m.title}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2 text-gray-600">{m.owner}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{m.source_count}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{m.enrollment_count}</td>
                      <td className="px-4 py-2 text-right" style={{ color: accent }}>{(m.total_answers + m.dozent.exercises).toLocaleString("de-DE")}</td>
                      <td className="px-4 py-2 text-right text-gray-600">{(m.chat_messages + m.dozent.messages).toLocaleString("de-DE")}</td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={7} className="px-0 py-0">
                          <div className="bg-gray-50 border-t border-gray-100">
                            {m.students.length === 0 ? (
                              <p className="px-8 py-3 text-xs text-gray-400">Keine eingeschriebenen Teilnehmer</p>
                            ) : (
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="text-left text-gray-400 uppercase">
                                    <th className="pl-12 pr-4 py-2">Student</th>
                                    <th className="px-4 py-2 text-right">Übungen</th>
                                    <th className="px-4 py-2 text-right">Richtig</th>
                                    <th className="px-4 py-2 text-right">Lerntools</th>
                                    <th className="px-4 py-2 text-right">Sprachtr.</th>
                                    <th className="px-4 py-2 text-right">Chat</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {m.students.map((s) => (
                                    <tr key={s.name} className="border-t border-gray-100 hover:bg-gray-100/50">
                                      <td className="pl-12 pr-4 py-2 text-gray-700">{s.name}</td>
                                      <td className="px-4 py-2 text-right text-gray-600">{s.answers.toLocaleString("de-DE")}</td>
                                      <td className="px-4 py-2 text-right text-green-600">{s.correct.toLocaleString("de-DE")}</td>
                                      <td className="px-4 py-2 text-right" style={{ color: "var(--kb)" }}>{s.lerntools}</td>
                                      <td className="px-4 py-2 text-right" style={{ color: "var(--st)" }}>{s.sprachtraining}</td>
                                      <td className="px-4 py-2 text-right text-gray-600">{s.chat_messages}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
              {data.module_stats.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-gray-400">Keine Module vorhanden</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
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
          className="flex-1 min-w-[200px] text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title="Von"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title="Bis"
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value={50}>50 pro Seite</option>
          <option value={100}>100 pro Seite</option>
        </select>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {total} Ergebnis{total !== 1 ? "se" : ""}
        </span>
      </div>

      {/* Table */}
      {loading ? <Spinner className="flex justify-center py-12" /> : jobs.length === 0 ? (
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
                    ? "bg-primary text-white border-primary"
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

// --- Reusable provider toggle row ---
function ProviderToggle({ label, enabled, configured, available, envHint, saving, settingKey, onToggle }: {
  label: string; enabled: boolean; configured: boolean; available?: boolean; envHint?: string;
  saving: boolean; settingKey: string; onToggle: (key: string, val: boolean) => void;
}) {
  const statusText = !configured
    ? "Nicht konfiguriert."
    : !enabled
      ? "Deaktiviert — wird nicht angezeigt."
      : available === false
        ? "Aktiviert — Server nicht erreichbar."
        : "Aktiv — als Anbieter wählbar.";
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm text-gray-700">{label}</p>
        <p className="text-xs text-gray-500 mt-0.5">{statusText}</p>
        {!configured && envHint && (
          <p className="mt-1 text-xs text-gray-400"><code className="font-mono">{envHint}</code> nicht gesetzt</p>
        )}
      </div>
      <button
        onClick={() => onToggle(settingKey, !enabled)}
        disabled={saving || !configured}
        title={!configured && envHint ? `${envHint} ist nicht in .env gesetzt` : undefined}
        className={`relative shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
          enabled ? "bg-primary" : "bg-gray-300"
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
          enabled ? "translate-x-5" : "translate-x-0"
        }`} />
      </button>
    </div>
  );
}

function ProviderSection({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="border border-gray-200 rounded-xl bg-white p-5">
      <p className="text-sm font-medium text-gray-800 mb-1">{title}</p>
      {hint && <p className="text-xs text-gray-400 mb-4">{hint}</p>}
      {!hint && <div className="mb-3" />}
      <div className="space-y-4">
        {React.Children.toArray(children).flatMap((child, i, arr) =>
          i < arr.length - 1
            ? [child, <div key={`sep-${i}`} className="border-t border-gray-100" />]
            : [child]
        )}
      </div>
    </div>
  );
}

// --- Settings: General toggles ---
function GeneralSettingsSection() {
  const [whitelistEnabled, setWhitelistEnabled] = useState<boolean | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [s, setS] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/admin/settings", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        setWhitelistEnabled(d.whitelist_enabled ?? true);
        setS(d);
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

  const toggle = (key: string, val: boolean) => {
    setS((prev) => ({ ...prev, [key]: val }));
    patch({ [key]: val });
  };

  const P = (props: Omit<Parameters<typeof ProviderToggle>[0], "saving" | "onToggle">) => (
    <ProviderToggle {...props} saving={saving} onToggle={toggle} />
  );

  if (whitelistEnabled === null) return <Spinner className="flex justify-center py-12" />;

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
              whitelistEnabled ? "bg-primary" : "bg-gray-300"
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

      {/* TTS-Anbieter */}
      <ProviderSection title="Text-to-Speech">
        <P label="ElevenLabs" settingKey="elevenlabs_enabled" enabled={s.elevenlabs_enabled ?? false} configured={s.elevenlabs_configured ?? false} envHint="ELEVENLABS_API_KEY" />
        <P label="Kokoro TTS" settingKey="kokoro_enabled" enabled={s.kokoro_enabled ?? false} configured={s.kokoro_configured ?? false} available={s.kokoro_available} envHint="KOKORO_BASE_URL" />
        <P label="THL myLab (XTTS-v2)" settingKey="mylab_enabled" enabled={s.mylab_enabled ?? false} configured={s.mylab_configured ?? false} available={s.mylab_available} envHint="MYLAB_TTS_BASE_URL" />
        <P label="Thorsten (deutsch, lokal)" settingKey="thorsten_enabled" enabled={s.thorsten_enabled ?? false} configured={s.thorsten_configured ?? false} available={s.thorsten_available} envHint="THORSTEN_BASE_URL" />
      </ProviderSection>

      {/* Transkription */}
      <ProviderSection title="Transkription (Speech-to-Text)" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (Whisper)" settingKey="kisski_whisper_enabled" enabled={s.kisski_whisper_enabled ?? true} configured={s.kisski_whisper_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Whisper-3-large)" settingKey="mylab_whisper_enabled" enabled={s.mylab_whisper_enabled ?? false} configured={s.mylab_whisper_configured ?? false} available={s.mylab_whisper_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      {/* Embeddings */}
      <ProviderSection title="Embeddings (KI-Tutor)" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (e5-mistral-7b)" settingKey="kisski_embedding_enabled" enabled={s.kisski_embedding_enabled ?? true} configured={s.kisski_embedding_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (qwen3-embedding-4b)" settingKey="mylab_embedding_enabled" enabled={s.mylab_embedding_enabled ?? false} configured={s.mylab_embedding_configured ?? false} available={s.mylab_embedding_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      {/* Bild-Generierung */}
      <ProviderSection title="Bild-Generierung" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (Flux)" settingKey="kisski_image_gen_enabled" enabled={s.kisski_image_gen_enabled ?? true} configured={s.kisski_image_gen_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Flux.1-dev)" settingKey="mylab_image_gen_enabled" enabled={s.mylab_image_gen_enabled ?? false} configured={s.mylab_image_gen_configured ?? false} available={s.mylab_image_gen_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      {/* Bild-Analyse */}
      <ProviderSection title="Bild-Analyse" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (qwen3-vl)" settingKey="kisski_image_analyze_enabled" enabled={s.kisski_image_analyze_enabled ?? true} configured={s.kisski_image_analyze_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (qwen3-vl-8b)" settingKey="mylab_image_analyze_enabled" enabled={s.mylab_image_analyze_enabled ?? false} configured={s.mylab_image_analyze_configured ?? false} available={s.mylab_image_analyze_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      {/* Bild-Bearbeitung */}
      <ProviderSection title="Bild-Bearbeitung" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (Flux)" settingKey="kisski_image_edit_enabled" enabled={s.kisski_image_edit_enabled ?? true} configured={s.kisski_image_edit_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Flux.1-Kontext)" settingKey="mylab_image_edit_enabled" enabled={s.mylab_image_edit_enabled ?? false} configured={s.mylab_image_edit_configured ?? false} available={s.mylab_image_edit_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      {/* OCR */}
      <ProviderSection title="OCR (Texterkennung)" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (Docling)" settingKey="kisski_ocr_enabled" enabled={s.kisski_ocr_enabled ?? true} configured={s.kisski_ocr_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (Nanonets OCR2 3B)" settingKey="mylab_ocr_enabled" enabled={s.mylab_ocr_enabled ?? false} configured={s.mylab_ocr_configured ?? false} available={s.mylab_ocr_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>

      {/* LLM Chat */}
      <ProviderSection title="LLM Chat" hint="KISSKI = primär, THL myLab = Fallback bei Ausfall">
        <P label="KISSKI (Mistral / Qwen)" settingKey="kisski_llm_enabled" enabled={s.kisski_llm_enabled ?? true} configured={s.kisski_llm_configured ?? false} envHint="KISSKI_API_KEY" />
        <P label="THL myLab (GPT OSS 120B)" settingKey="mylab_llm_enabled" enabled={s.mylab_llm_enabled ?? false} configured={s.mylab_llm_configured ?? false} available={s.mylab_llm_available} envHint="MYLAB_BASE_URL" />
      </ProviderSection>
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

  if (!tools) return <Spinner className="flex justify-center py-12" />;

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
                tool.enabled ? "bg-primary" : "bg-gray-300"
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

  if (loading) return <Spinner className="flex justify-center py-12" />;

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
                ? "border-gray-300 bg-white text-gray-800 focus:ring-2 focus:ring-primary"
                : "border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed select-none"
            }`}
          />
          {p.editable && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => save(p.key)}
                disabled={saving === p.key}
                className="text-sm bg-primary text-white px-4 py-1.5 rounded-lg hover:bg-primary-hover disabled:opacity-50"
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


// ─── Tab: Kontingente ─────────────────────────────────────────────────────────

interface QuotaEntry {
  quota_type: string;
  label: string;
  used: number;
  limit: number;
  limit_is_unlimited: boolean;
  override: number | null;
  reset_at: string | null;
}

interface QuotaUser {
  user_id: number;
  ldap_username: string;
  display_name: string;
  quotas: QuotaEntry[];
  global_reset_at: string | null;
}

interface QuotaDefaults {
  [key: string]: { limit: number; window_hours: number; label: string };
}

function QuotaTab({ targetUserId, onConsumed, onBack }: { targetUserId: number | null; onConsumed: () => void; onBack: () => void }) {
  const [defaults, setDefaults] = useState<QuotaDefaults>({});
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<QuotaUser | null>(null);
  const [overrideInputs, setOverrideInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const defaultsRes = await fetch("/api/admin/quota/defaults", { credentials: "include" });
      const defs = await defaultsRes.json();
      setDefaults(defs.defaults ?? {});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (targetUserId === null) return;
    openUser({ user_id: targetUserId, display_name: "", ldap_username: "", quotas: [], global_reset_at: null });
    onConsumed();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetUserId]);

  const openUser = async (u: QuotaUser) => {
    const res = await fetch(`/api/admin/quota/users/${u.user_id}`, { credentials: "include" });
    const data = await res.json();
    const inputs: Record<string, string> = {};
    for (const q of data.quotas ?? []) {
      inputs[q.quota_type] = q.override !== null ? String(q.override) : "";
    }
    setOverrideInputs(inputs);
    setSelectedUser({ ...u, quotas: data.quotas ?? u.quotas, global_reset_at: data.global_reset_at ?? null });
  };

  const saveOverride = async (quotaType: string, value: string) => {
    if (!selectedUser) return;
    const limit = value === "" ? null : parseInt(value, 10);
    setSaving(quotaType);
    try {
      if (limit === null) {
        await fetch(`/api/admin/quota/users/${selectedUser.user_id}/${quotaType}/override`, {
          method: "DELETE", credentials: "include",
        });
      } else {
        await fetch(`/api/admin/quota/users/${selectedUser.user_id}/${quotaType}/override`, {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ limit_value: limit }),
        });
      }
      await Promise.all([openUser(selectedUser), load()]);
    } finally {
      setSaving(null);
    }
  };

  const resetQuota = async (quotaType: string) => {
    if (!selectedUser) return;
    setSaving(quotaType + "_reset");
    try {
      await fetch(`/api/admin/quota/users/${selectedUser.user_id}/${quotaType}/reset`, {
        method: "POST", credentials: "include",
      });
      await Promise.all([openUser(selectedUser), load()]);
    } finally {
      setSaving(null);
    }
  };

  if (loading) return <Spinner className="flex justify-center py-12" />;

  if (selectedUser) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <button onClick={() => { setSelectedUser(null); onBack(); }} className="text-sm text-primary hover:underline">
            ← Zurück
          </button>
          <span className="text-sm text-gray-500">|</span>
          <span className="text-sm font-medium text-gray-800">{selectedUser.display_name}</span>
        </div>

        {selectedUser.global_reset_at && (
          <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2.5">
            <span>Globaler Reset aktiv — alle Tools werden zurückgesetzt ab {new Date(selectedUser.global_reset_at).toLocaleString("de-DE", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", timeZone: "Europe/Berlin" })} Uhr.</span>
          </div>
        )}

        <div className="border border-gray-200 rounded-xl bg-white overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Tool</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Verbraucht</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Limit (Standard)</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Override</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">Reset</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {selectedUser.quotas.map((q) => {
                const def = defaults[q.quota_type];
                const effectiveLimit = q.limit_is_unlimited ? "∞" : String(q.limit);
                const pct = q.limit_is_unlimited ? 0 : Math.min(100, Math.round((q.used / q.limit) * 100));
                return (
                  <tr key={q.quota_type} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-800">{q.label}</td>
                    <td className="px-4 py-3 text-gray-700">
                      <div className="flex items-center gap-2">
                        <span>{q.used} / {effectiveLimit}</span>
                        {!q.limit_is_unlimited && (
                          <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-amber-400" : "bg-blue-500"}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        )}
                      </div>
                      {!q.limit_is_unlimited && q.used >= q.limit && (
                        <p className="text-xs text-amber-600 mt-0.5">Gesperrt</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{def ? `${def.limit} / ${def.window_hours}h` : "–"}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          min="-1"
                          value={overrideInputs[q.quota_type] ?? ""}
                          onChange={(e) => setOverrideInputs((prev) => ({ ...prev, [q.quota_type]: e.target.value }))}
                          placeholder="Standard"
                          className="w-24 border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:border-primary"
                        />
                        <button
                          onClick={() => saveOverride(q.quota_type, overrideInputs[q.quota_type] ?? "")}
                          disabled={saving === q.quota_type}
                          className="text-xs text-primary hover:underline disabled:opacity-50"
                        >
                          Speichern
                        </button>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">-1 = unlimitiert, leer = Standard</p>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => resetQuota(q.quota_type)}
                        disabled={saving === q.quota_type + "_reset" || q.used === 0}
                        className="text-xs text-red-600 hover:underline disabled:opacity-40"
                      >
                        Zurücksetzen
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="border border-gray-200 rounded-xl bg-white p-4">
          <p className="text-xs font-medium text-gray-500 mb-3">Standard-Limits (global)</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(defaults).map(([type, def]) => (
              <div key={type} className="text-xs text-gray-600">
                <span className="font-medium">{def.label}:</span> {def.limit} / {def.window_hours}h
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="text-center py-12 text-sm text-gray-500">
      Bitte einen User über <span className="font-medium text-gray-700">Alle User → Kontingente →</span> auswählen.
    </div>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("settings");
  const [checking, setChecking] = useState(true);
  const [adminEmail, setAdminEmail] = useState("");
  const [quotaTargetId, setQuotaTargetId] = useState<number | null>(null);
  const router = useRouter();

  const openQuotaForUser = (userId: number) => {
    setQuotaTargetId(userId);
    setTab("quota");
  };

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
    { key: "stats", label: "Statistiken" },
    { key: "ki-tutor", label: "KI-Tutor" },
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
                  ? "border-primary text-primary"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "pending" && <PendingTab />}
        {tab === "whitelist" && <WhitelistTab adminEmail={adminEmail} />}
        {tab === "users" && <UsersTab onOpenQuota={openQuotaForUser} />}
        {tab === "jobs" && <JobsTab />}
        {tab === "stats" && <StatsTab />}
        {tab === "ki-tutor" && <KiTutorTab />}
        {tab === "settings" && <SettingsTab />}
        {tab === "prompts" && <PromptsTab />}
        {tab === "quota" && <QuotaTab targetUserId={quotaTargetId} onConsumed={() => setQuotaTargetId(null)} onBack={() => setTab("users")} />}
      </main>
    </>
  );
}
