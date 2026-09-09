"use client";

/** The permission table without a save button, every click is its own call. */

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Plus } from "@phosphor-icons/react";

import { genericErrorMessage, parseDetail } from "@/lib/api";
import Checkbox from "@/components/ui/Checkbox";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import { InlineRename } from "@/components/ui/InlineRename";
import RoleMenu from "./RoleMenu";
import { byChapter } from "./_chapters";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";

interface Group {
  key: string;
  /** Chapter the group sits in, without it the table stays single level. */
  chapter?: string;
  permissions: string[];
}

interface SystemRole {
  key: string;
  permissions: string[];
}

interface CustomRole {
  id: number;
  name: string;
  permissions: string[];
}

interface MatrixResponse {
  groups: Group[];
  system_roles: SystemRole[];
  custom_roles: CustomRole[];
  grantable: string[];
}

/** A column is either a system role or a custom one. */
type Column =
  | { kind: "system"; key: string; permissions: Set<string> }
  | { kind: "custom"; role: CustomRole; permissions: Set<string> };

export default function PermissionMatrix() {
  const t = useTranslations("admin.roles");
  const tp = useTranslations("admin.permissions");
  // Two rows speak of course rooms, whose label the operator sets.
  const ws = useWorkspaceLabel();
  // The catalogue comes from the server, the keys are only known at runtime.
  const permLabel = (key: string) =>
    (tp as unknown as (k: string, v?: Record<string, string>) => string)(key, {
      label: ws.singular,
      plural: ws.plural,
    });

  const [data, setData] = useState<MatrixResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  // A separate error for the dialog, the general one sits behind it.
  const [createError, setCreateError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<CustomRole | null>(null);
  // Prevents double clicks from overtaking each other.
  const [busy, setBusy] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/roles", { credentials: "include" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(parseDetail(body.detail, genericErrorMessage()));
      }
      setData(await res.json());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const columns: Column[] = useMemo(() => {
    if (!data) return [];
    return [
      ...data.system_roles.map(
        (r): Column => ({ kind: "system", key: r.key, permissions: new Set(r.permissions) }),
      ),
      ...data.custom_roles.map(
        (r): Column => ({ kind: "custom", role: r, permissions: new Set(r.permissions) }),
      ),
    ];
  }, [data]);

  const grantable = useMemo(() => new Set(data?.grantable ?? []), [data]);

  async function toggle(role: CustomRole, key: string, next: boolean) {
    const cell = `${role.id}:${key}`;
    if (busy.has(cell)) return;
    setBusy((b) => new Set(b).add(cell));
    setError(null);

    // Flip first, then ask, on a refusal it is reverted.
    const rollback = role.permissions;
    applyPermissions(role.id, next ? [...rollback, key] : rollback.filter((k) => k !== key));

    try {
      const res = await fetch(`/api/admin/roles/${role.id}/permissions`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, granted: next }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(parseDetail(body.detail, genericErrorMessage()));
      }
      const saved = await res.json();
      applyPermissions(role.id, saved.permissions);
    } catch (e) {
      applyPermissions(role.id, rollback);
      setError(e instanceof Error ? e.message : t("saveFailed"));
    } finally {
      setBusy((b) => {
        const next2 = new Set(b);
        next2.delete(cell);
        return next2;
      });
    }
  }

  function applyPermissions(roleId: number, permissions: string[]) {
    setData((d) =>
      d
        ? {
            ...d,
            custom_roles: d.custom_roles.map((r) =>
              r.id === roleId ? { ...r, permissions } : r,
            ),
          }
        : d,
    );
  }

  async function createRole() {
    const name = newName.trim();
    if (!name) return;
    setCreateError(null);
    try {
      const res = await fetch("/api/admin/roles", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, permissions: [] }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(parseDetail(body.detail, genericErrorMessage()));
      }
      setCreating(false);
      setNewName("");
      await load();
    } catch (e) {
      // The dialog stays open so the name can be fixed right away.
      setCreateError(e instanceof Error ? e.message : "error");
    }
  }

  async function rename(roleId: number, name: string) {
    const res = await fetch(`/api/admin/roles/${roleId}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(parseDetail(body.detail, genericErrorMessage()));
    }
    setData((d) =>
      d
        ? {
            ...d,
            custom_roles: d.custom_roles.map((r) => (r.id === roleId ? { ...r, name } : r)),
          }
        : d,
    );
  }

  async function remove(role: CustomRole) {
    setError(null);
    try {
      const res = await fetch(`/api/admin/roles/${role.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(parseDetail(body.detail, genericErrorMessage()));
      }
      setDeleting(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "error");
    }
  }

  if (loading || !data) {
    return <Spinner className="flex justify-center py-12" />;
  }

  const headCell =
    "px-3 py-2 text-center align-bottom text-xs font-semibold text-foreground whitespace-nowrap";

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm text-muted max-w-2xl">{t("matrixHint")}</p>
        <button
          type="button"
          onClick={() => { setCreateError(null); setNewName(""); setCreating(true); }}
          className="shrink-0 flex items-center gap-1.5 px-4 py-2 text-sm btn-primary rounded-md transition-colors"
        >
          <Plus size={14} weight="bold" />
          {t("newRole")}
        </button>
      </div>

      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}

      {/* Waagerecht scrollen, aber die Funktionsspalte bleibt stehen. Ohne sie
          weiß bei zehn Rollen niemand mehr, in welcher Zeile er klickt. */}
      <div className="overflow-x-auto border border-border-soft rounded-xl">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-surface">
              <th className="sticky left-0 z-10 bg-surface px-3 py-2 text-left text-xs font-semibold text-foreground min-w-[16rem]">
                {t("functionColumn")}
              </th>
              {columns.map((col) => (
                <th
                  key={col.kind === "system" ? `sys-${col.key}` : `own-${col.role.id}`}
                  className={headCell}
                  scope="col"
                >
                  {col.kind === "system" ? (
                    <span title={t(`systemRoleHint.${col.key}` as never)}>
                      {t(`roleName.${col.key}` as never)}
                    </span>
                  ) : renaming === col.role.id ? (
                    <InlineRename
                      value={col.role.name}
                      onSave={(next) => rename(col.role.id, next)}
                      onCancel={() => setRenaming(null)}
                      errorText={t("renameFailed")}
                    />
                  ) : (
                    <span className="inline-flex items-center gap-1">
                      {col.role.name}
                      <RoleMenu
                        onRename={() => setRenaming(col.role.id)}
                        onDelete={() => setDeleting(col.role)}
                      />
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {byChapter(data.groups).map((block, i) => (
              <Fragment key={block.chapter ?? `block-${i}`}>
                {block.chapter && (
                  <tr>
                    <th
                      colSpan={columns.length + 1}
                      scope="colgroup"
                      className="sticky left-0 bg-kb px-3 py-2 text-left text-xs font-bold uppercase tracking-[0.12em] text-on-accent"
                    >
                      {permLabel(`chapter.${block.chapter}`)}
                    </th>
                  </tr>
                )}
                {block.groups.map((group) => (
                  <GroupRows
                    key={group.key}
                    group={group}
                    columns={columns}
                    grantable={grantable}
                    busy={busy}
                    label={permLabel}
                    groupLabel={permLabel(`group.${group.key}`)}
                    indent={!!block.chapter}
                    onToggle={toggle}
                    lockedLabel={t("locked")}
                  />
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-soft">{t("systemHint")}</p>

      <Modal
        open={creating}
        onClose={() => { setCreating(false); setCreateError(null); }}
        title={t("newRole")}
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => { setCreating(false); setCreateError(null); }}
              className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
            >
              {t("cancel")}
            </button>
            <button
              type="button"
              onClick={createRole}
              disabled={!newName.trim()}
              className="px-4 py-2 text-sm btn-primary rounded-md transition-colors disabled:opacity-60"
            >
              {t("save")}
            </button>
          </div>
        }
      >
        <label className="block space-y-1">
          <span className="text-xs uppercase tracking-wide text-muted">{t("name")}</span>
          <input
            type="text"
            autoFocus
            value={newName}
            onChange={(e) => { setNewName(e.target.value); setCreateError(null); }}
            onKeyDown={(e) => {
              if (e.key === "Enter") createRole();
            }}
            className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
        </label>
        {createError && (
          <p
            role="alert"
            className="mt-2 text-xs rounded-md px-2 py-1"
            style={{
              backgroundColor: "var(--error-bg)",
              border: "1px solid var(--error-border)",
              color: "var(--error-strong)",
            }}
          >
            {createError}
          </p>
        )}
        <p className="mt-3 text-xs text-muted">{t("newRoleHint")}</p>
      </Modal>

      <Modal
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={t("delete")}
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setDeleting(null)}
              className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
            >
              {t("cancel")}
            </button>
            <button
              type="button"
              onClick={() => deleting && remove(deleting)}
              className="px-4 py-2 text-sm bg-error text-white rounded-md"
            >
              {t("delete")}
            </button>
          </div>
        }
      >
        <p className="text-sm text-foreground-soft">
          {t("confirmDelete", { name: deleting?.name ?? "" })}
        </p>
      </Modal>
    </div>
  );
}

function GroupRows({
  group,
  columns,
  grantable,
  busy,
  label,
  groupLabel,
  indent,
  onToggle,
  lockedLabel,
}: {
  group: Group;
  columns: Column[];
  grantable: Set<string>;
  busy: Set<string>;
  label: (key: string) => string;
  groupLabel: string;
  /** Under a chapter row, group and rows indent by one level. */
  indent: boolean;
  onToggle: (role: CustomRole, key: string, next: boolean) => void;
  lockedLabel: string;
}) {
  const pad = indent ? "pl-7" : "px-3";
  return (
    <>
      <tr>
        <th
          colSpan={columns.length + 1}
          scope="colgroup"
          className={`sticky left-0 bg-surface-dim ${pad} pr-3 py-1.5 text-left text-2xs font-semibold uppercase tracking-[0.09em] text-muted`}
        >
          {groupLabel}
        </th>
      </tr>
      {group.permissions.map((key) => (
        <tr key={key} className="border-t border-border-soft hover:bg-surface/60">
          <th
            scope="row"
            className={`sticky left-0 z-10 bg-background ${pad} pr-3 py-2 text-left font-normal text-foreground`}
          >
            {label(key)}
          </th>
          {columns.map((col) => {
            if (col.kind === "system") {
              const on = col.permissions.has(key);
              return (
                <td key={`sys-${col.key}`} className="px-3 py-2 text-center">
                  {/* Systemrollen sind fest. Kein Kästchen, nur ein Haken oder
                      nichts, damit gar nicht erst jemand draufklickt. */}
                  <span
                    className="inline-flex items-center justify-center text-muted"
                    title={lockedLabel}
                    aria-label={lockedLabel}
                  >
                    {on ? <Check size={14} weight="bold" /> : <span aria-hidden>·</span>}
                  </span>
                </td>
              );
            }
            const cell = `${col.role.id}:${key}`;
            const mayGrant = grantable.has(key);
            const checked = col.permissions.has(key);
            return (
              <td key={`own-${col.role.id}`} className="px-3 py-2">
                <div className="flex justify-center">
                  <Checkbox
                    checked={checked}
                    // Taking away is always allowed, granting only what you hold yourself.
                    disabled={busy.has(cell) || (!checked && !mayGrant)}
                    onChange={(next) => onToggle(col.role, key, next)}
                    label={undefined}
                  />
                </div>
              </td>
            );
          })}
        </tr>
      ))}
    </>
  );
}
