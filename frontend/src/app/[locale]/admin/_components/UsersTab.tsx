"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Users } from "@phosphor-icons/react";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate } from "@/lib/format";
import type { AdminUser } from "../_shared";
import CreateLdapUserDialog from "./CreateLdapUserDialog";

export default function UsersTab({ onOpenQuota }: { onOpenQuota: (userId: number) => void }) {
  const t = useTranslations("admin");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [roleOptions, setRoleOptions] = useState<{ value: string; label: string; customId: number | null }[]>([]);
  const [adminEmail, setAdminEmail] = useState<string>("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [allowLdapCreate, setAllowLdapCreate] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const pageSizeOptions = useMemo(
    () => [
      { value: "50", label: t("users.pageSize", { n: 50 }) },
      { value: "100", label: t("users.pageSize", { n: 100 }) },
    ],
    [t],
  );

  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(q), 350);
    return () => clearTimeout(id);
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
  }, [limit, offset, debouncedQ, dateFrom, dateTo, refreshKey]);

  useEffect(() => {
    fetch("/api/admin/roles", { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        if (!d) return;
        const opts = [
          { value: "admin", label: t("roles.roleAdmin"), customId: null as number | null },
          { value: "staff", label: t("roles.roleStaff"), customId: null as number | null },
          { value: "user", label: t("roles.roleUser"), customId: null as number | null },
          ...d.custom_roles.map((r: { id: number; name: string }) => ({
            value: `custom:${r.id}`,
            label: r.name,
            customId: r.id,
          })),
        ];
        setRoleOptions(opts);
      });
    fetch("/auth/status", { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((s) => {
        if (s?.email) setAdminEmail(String(s.email).toLowerCase());
        setAllowLdapCreate(Boolean(s?.permissions?.allow_ldap_user_create));
      });
  }, [t]);

  async function changeRole(userId: number, value: string) {
    const opt = roleOptions.find((o) => o.value === value);
    if (!opt) return;
    const role = opt.value.startsWith("custom:") ? "custom" : opt.value;
    const customRoleId = opt.customId;
    const res = await fetch(`/api/admin/users/${userId}/role`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, custom_role_id: customRoleId }),
    });
    if (res.ok) {
      setUsers((prev) => prev.map((u) =>
        u.id === userId
          ? { ...u, role: role as AdminUser["role"], custom_role_id: customRoleId }
          : u,
      ));
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("users.searchPlaceholder")}
          className="flex-1 min-w-50 text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title={t("users.from")}
          className="text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title={t("users.to")}
          className="text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
        />
        <Select
          value={String(limit)}
          onChange={(v) => setLimit(Number(v))}
          options={pageSizeOptions}
          className="w-40"
        />
        <span className="text-xs text-muted-soft whitespace-nowrap">{t("users.totalUsers", { n: total })}</span>
        {allowLdapCreate && (
          <button
            type="button"
            onClick={() => setShowCreateDialog(true)}
            className="px-3 py-2 text-sm bg-kb text-white rounded-md whitespace-nowrap"
          >
            {t("createLdapUser.buttonLabel")}
          </button>
        )}
      </div>

      {loading ? (
        <Spinner className="flex justify-center py-12" />
      ) : users.length === 0 ? (
        <EmptyState
          size="lg"
          icon={<Users size={32} weight="bold" />}
          text={t("users.empty")}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
            <thead className="bg-surface text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3 text-left">{t("users.colName")}</th>
                <th className="px-4 py-3 text-left">{t("users.colEmail")}</th>
                <th className="px-4 py-3 text-left">{t("users.colStatus")}</th>
                <th className="px-4 py-3 text-left">{t("roles.userRoleLabel")}</th>
                <th className="px-4 py-3 text-left">{t("users.colCreated")}</th>
                <th className="px-4 py-3 text-left">{t("users.colQuotas")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft bg-background">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">{u.display_name}</p>
                    <p className="text-xs text-muted-soft">{u.ldap_username}</p>
                  </td>
                  <td className="px-4 py-3 text-foreground-soft">
                    {u.email ?? <span className="text-border">-</span>}
                  </td>
                  <td className="px-4 py-3">
                    {u.active ? (
                      <span className="text-xs font-medium text-success-strong bg-success-bg px-2 py-0.5 rounded-full">
                        {t("users.active")}
                      </span>
                    ) : (
                      <span className="text-xs font-medium text-error bg-error-bg px-2 py-0.5 rounded-full">
                        {t("users.inactive")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {(() => {
                      const isEnvAdmin = !!u.email && u.email.toLowerCase() === adminEmail;
                      const currentValue =
                        u.role === "custom" && u.custom_role_id != null
                          ? `custom:${u.custom_role_id}`
                          : (u.role ?? "user");
                      if (isEnvAdmin) {
                        return (
                          <span
                            className="text-xs"
                            style={{ color: "var(--muted-soft)" }}
                            title={t("roles.envAdminLocked")}
                          >
                            {t("roles.roleAdmin")}
                          </span>
                        );
                      }
                      return (
                        <select
                          value={currentValue}
                          onChange={(e) => changeRole(u.id, e.target.value)}
                          className="text-xs border border-border rounded-md px-2 py-1 bg-background"
                        >
                          {roleOptions.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-3 text-muted-soft text-xs whitespace-nowrap">
                    {formatDate(u.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => onOpenQuota(u.id)}
                      className="text-xs text-kb hover:underline whitespace-nowrap"
                    >
                      {t("users.details")}
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
            className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
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
                className={`px-3 py-1.5 text-sm border-2 rounded-md transition-colors ${
                  page === currentPage
                    ? "bg-kb text-white border-kb"
                    : "border-border hover:border-[var(--kb)] hover:text-[var(--kb)]"
                }`}
              >
                {page}
              </button>
            );
          })}
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={currentPage === totalPages}
            className="px-3 py-1.5 text-sm border-2 border-border rounded-md transition-colors disabled:opacity-40 enabled:hover:border-[var(--kb)] enabled:hover:text-[var(--kb)]"
          >
            ›
          </button>
        </div>
      )}

      {showCreateDialog && (
        <CreateLdapUserDialog onClose={() => {
          setShowCreateDialog(false);
          setRefreshKey((k) => k + 1);
        }} />
      )}
    </div>
  );
}
