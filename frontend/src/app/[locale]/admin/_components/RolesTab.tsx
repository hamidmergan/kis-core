"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import RoleBuilderDialog from "./RoleBuilderDialog";

interface CustomRole {
  id: number;
  name: string;
  allow_aia: boolean;
  allowed_tools: string[];
}

interface RolesResponse {
  system_roles: string[];
  custom_roles: CustomRole[];
  available_tools: string[];
}

export default function RolesTab() {
  const t = useTranslations("admin.roles");
  const [data, setData] = useState<RolesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  // undefined = closed, null = creating, value = editing
  const [editing, setEditing] = useState<CustomRole | null | undefined>(undefined);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/roles", { credentials: "include" });
      if (res.ok) setData(await res.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function remove(role: CustomRole) {
    if (!confirm(t("confirmDelete"))) return;
    await fetch(`/api/admin/roles/${role.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    await load();
  }

  if (loading || !data) {
    return <Spinner className="flex justify-center py-12" />;
  }

  return (
    <div className="space-y-8">
      <section>
        <h3 className="text-base font-semibold mb-1">{t("system")}</h3>
        <p className="text-sm" style={{ color: "var(--muted)" }}>{t("systemHint")}</p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {data.system_roles.map((r) => (
            <li
              key={r}
              className="text-xs font-mono px-2 py-1 rounded-md"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
            >
              {r}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-semibold">{t("custom")}</h3>
          <button
            type="button"
            onClick={() => setEditing(null)}
            className="px-4 py-2 rounded-md text-sm font-medium btn-primary"
          >
            + {t("newRole")}
          </button>
        </div>

        {data.custom_roles.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}></p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border-soft rounded-xl overflow-hidden">
              <thead className="bg-surface text-xs text-muted uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">{t("name")}</th>
                  <th className="px-4 py-3 text-left">{t("allowAia")}</th>
                  <th className="px-4 py-3 text-left">{t("tools")}</th>
                  <th className="px-4 py-3 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-soft bg-background">
                {data.custom_roles.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-3 font-medium">{r.name}</td>
                    <td className="px-4 py-3">{r.allow_aia ? "+" : "-"}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: "var(--muted-soft)" }}>
                      {r.allowed_tools.length ? r.allowed_tools.join(", ") : "-"}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => setEditing(r)}
                        className="text-xs text-kb hover:underline mr-3"
                      >
                        {t("edit")}
                      </button>
                      <button
                        onClick={() => remove(r)}
                        className="text-xs hover:underline"
                        style={{ color: "var(--error)" }}
                      >
                        {t("delete")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {editing !== undefined && (
        <RoleBuilderDialog
          initial={editing}
          availableTools={data.available_tools}
          onClose={() => setEditing(undefined)}
          onSaved={() => { setEditing(undefined); load(); }}
        />
      )}
    </div>
  );
}
