"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "@/components/ui/Spinner";
import { formatDate } from "@/lib/format";
import type { PendingUser } from "../_shared";

export default function PendingTab() {
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

  useEffect(() => {
    load();
  }, [load]);

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
            <p className="text-xs text-gray-500 mt-0.5">
              {u.email ?? <span className="text-red-400">Keine Email</span>}
            </p>
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
