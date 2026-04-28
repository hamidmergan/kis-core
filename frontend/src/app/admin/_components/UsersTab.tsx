"use client";

import { useEffect, useState } from "react";
import Spinner from "@/components/ui/Spinner";
import { formatDate } from "@/lib/format";
import type { AdminUser } from "../_shared";

export default function UsersTab({ onOpenQuota }: { onOpenQuota: (userId: number) => void }) {
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

  useEffect(() => {
    setOffset(0);
  }, [debouncedQ, limit, dateFrom, dateTo]);

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
      .then((d) => {
        setUsers(d.users ?? []);
        setTotal(d.total ?? 0);
      })
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
        <span className="text-xs text-gray-400 whitespace-nowrap">{total} User</span>
      </div>

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : users.length === 0 ? (
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
                  <td className="px-4 py-3 text-gray-600">
                    {u.email ?? <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    {u.active ? (
                      <span className="text-xs font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                        Aktiv
                      </span>
                    ) : (
                      <span className="text-xs font-medium text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                        Inaktiv
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                    {formatDate(u.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => onOpenQuota(u.id)}
                      className="text-xs text-primary hover:underline whitespace-nowrap"
                    >
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
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-100"
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
                    : "border-gray-300 hover:bg-gray-100"
                }`}
              >
                {page}
              </button>
            );
          })}
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-40 hover:bg-gray-100"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}
