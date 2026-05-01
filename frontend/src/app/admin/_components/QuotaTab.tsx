"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "@/components/ui/Spinner";

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

interface QuotaTabProps {
  targetUserId: number | null;
  onConsumed: () => void;
  onBack: () => void;
}

export default function QuotaTab({ targetUserId, onConsumed, onBack }: QuotaTabProps) {
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

  useEffect(() => {
    load();
  }, [load]);

  const openUser = useCallback(async (u: QuotaUser) => {
    const res = await fetch(`/api/admin/quota/users/${u.user_id}`, { credentials: "include" });
    const data = await res.json();
    const inputs: Record<string, string> = {};
    for (const q of data.quotas ?? []) {
      inputs[q.quota_type] = q.override !== null ? String(q.override) : "";
    }
    setOverrideInputs(inputs);
    setSelectedUser({ ...u, quotas: data.quotas ?? u.quotas, global_reset_at: data.global_reset_at ?? null });
  }, []);

  useEffect(() => {
    if (targetUserId === null) return;
    openUser({
      user_id: targetUserId,
      display_name: "",
      ldap_username: "",
      quotas: [],
      global_reset_at: null,
    });
    onConsumed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetUserId]);

  const saveOverride = async (quotaType: string, value: string) => {
    if (!selectedUser) return;
    const limit = value === "" ? null : parseInt(value, 10);
    setSaving(quotaType);
    try {
      if (limit === null) {
        await fetch(`/api/admin/quota/users/${selectedUser.user_id}/${quotaType}/override`, {
          method: "DELETE",
          credentials: "include",
        });
      } else {
        await fetch(`/api/admin/quota/users/${selectedUser.user_id}/${quotaType}/override`, {
          method: "POST",
          credentials: "include",
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
        method: "POST",
        credentials: "include",
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
          <button
            onClick={() => {
              setSelectedUser(null);
              onBack();
            }}
            className="text-sm text-kb hover:underline"
          >
            ← Zurück
          </button>
          <span className="text-sm text-muted">|</span>
          <span className="text-sm font-medium text-foreground">{selectedUser.display_name}</span>
        </div>

        {selectedUser.global_reset_at && (
          <div className="flex items-center gap-2 text-xs text-warn-strong bg-warn-bg border border-warn-border rounded-lg px-4 py-2.5">
            <span>
              Globaler Reset aktiv - alle Tools werden zurückgesetzt ab{" "}
              {new Date(selectedUser.global_reset_at).toLocaleString("de-DE", {
                hour: "2-digit",
                minute: "2-digit",
                day: "2-digit",
                month: "2-digit",
                timeZone: "Europe/Berlin",
              })}{" "}
              Uhr.
            </span>
          </div>
        )}

        <div className="border border-border-soft rounded-xl bg-white overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-surface border-b border-border-soft">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted">Tool</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted">Verbraucht</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted">Limit (Standard)</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted">Override</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-muted">Reset</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft">
              {selectedUser.quotas.map((q) => {
                const def = defaults[q.quota_type];
                const effectiveLimit = q.limit_is_unlimited ? "∞" : String(q.limit);
                const pct = q.limit_is_unlimited
                  ? 0
                  : Math.min(100, Math.round((q.used / q.limit) * 100));
                return (
                  <tr key={q.quota_type} className="hover:bg-surface">
                    <td className="px-4 py-3 font-medium text-foreground">{q.label}</td>
                    <td className="px-4 py-3 text-foreground-soft">
                      <div className="flex items-center gap-2">
                        <span>
                          {q.used} / {effectiveLimit}
                        </span>
                        {!q.limit_is_unlimited && (
                          <div className="w-16 h-1.5 bg-surface-dim rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${pct >= 100 ? "bg-error" : pct >= 80 ? "bg-warn-border" : "bg-info"}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        )}
                      </div>
                      {!q.limit_is_unlimited && q.used >= q.limit && (
                        <p className="text-xs text-warn mt-0.5">Gesperrt</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {def ? `${def.limit} / ${def.window_hours}h` : "-"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          min="-1"
                          value={overrideInputs[q.quota_type] ?? ""}
                          onChange={(e) =>
                            setOverrideInputs((prev) => ({ ...prev, [q.quota_type]: e.target.value }))
                          }
                          placeholder="Standard"
                          className="w-24 border border-border rounded px-2 py-1 text-sm focus:outline-none focus:border-kb"
                        />
                        <button
                          onClick={() => saveOverride(q.quota_type, overrideInputs[q.quota_type] ?? "")}
                          disabled={saving === q.quota_type}
                          className="text-xs text-kb hover:underline disabled:opacity-50"
                        >
                          Speichern
                        </button>
                      </div>
                      <p className="text-xs text-muted-soft mt-0.5">-1 = unlimitiert, leer = Standard</p>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => resetQuota(q.quota_type)}
                        disabled={saving === q.quota_type + "_reset" || q.used === 0}
                        className="text-xs text-error hover:underline disabled:opacity-40"
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

        <div className="border border-border-soft rounded-xl bg-white p-4">
          <p className="text-xs font-medium text-muted mb-3">Standard-Limits (global)</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(defaults).map(([type, def]) => (
              <div key={type} className="text-xs text-foreground-soft">
                <span className="font-medium">{def.label}:</span> {def.limit} / {def.window_hours}h
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="text-center py-12 text-sm text-muted">
      Bitte einen User über{" "}
      <span className="font-medium text-foreground-soft">Alle User → Kontingente →</span> auswählen.
    </div>
  );
}
