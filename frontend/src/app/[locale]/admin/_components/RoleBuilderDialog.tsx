"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";

type AiaAccess = "none" | "read" | "edit";

interface CustomRole {
  id?: number;
  name: string;
  aia_access?: AiaAccess;
  allowed_tools: string[];
}

interface Props {
  initial: CustomRole | null;
  availableTools: string[];
  onClose: () => void;
  onSaved: () => void;
}

// Link-based read access is a universal baseline now, so a tools-only "none"
// role is no longer distinct from "read". Offer only read vs edit; legacy
// "none" roles in the DB are normalized to "read" below.
const AIA_OPTIONS: { value: Exclude<AiaAccess, "none">; labelKey: "aiaRead" | "aiaEdit" }[] = [
  { value: "read", labelKey: "aiaRead" },
  { value: "edit", labelKey: "aiaEdit" },
];

const normalizeAia = (a?: AiaAccess): Exclude<AiaAccess, "none"> =>
  a === "edit" ? "edit" : "read";

export default function RoleBuilderDialog({ initial, availableTools, onClose, onSaved }: Props) {
  const t = useTranslations("admin.roles");
  const tTools = useTranslations("toolsSidebar.items");
  const ws = useWorkspaceLabel();
  const [name, setName] = useState(initial?.name ?? "");
  const [aiaAccess, setAiaAccess] = useState<AiaAccess>(normalizeAia(initial?.aia_access));
  const [tools, setTools] = useState<Set<string>>(new Set(initial?.allowed_tools ?? []));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleTool(key: string) {
    const next = new Set(tools);
    if (next.has(key)) next.delete(key); else next.add(key);
    setTools(next);
  }

  const allToolsCount = availableTools.length;
  const selectedToolsCount = availableTools.filter((k) => tools.has(k)).length;
  const allSelected = allToolsCount > 0 && selectedToolsCount === allToolsCount;
  const someSelected = selectedToolsCount > 0 && !allSelected;
  const toggleAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (toggleAllRef.current) toggleAllRef.current.indeterminate = someSelected;
  }, [someSelected]);

  function toggleAllTools() {
    setTools(allSelected ? new Set() : new Set(availableTools));
  }

  async function save() {
    setSaving(true);
    setError(null);
    const payload = {
      name: name.trim(),
      aia_access: aiaAccess,
      allowed_tools: Array.from(tools),
    };
    const url = initial?.id ? `/api/admin/roles/${initial.id}` : `/api/admin/roles`;
    const method = initial?.id ? "PUT" : "POST";
    try {
      const res = await fetch(url, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="bg-background border border-border rounded-xl shadow-xl w-full max-w-md p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold">{initial?.id ? t("edit") : t("newRole")}</h2>

        <div className="space-y-1">
          <label className="text-xs uppercase tracking-wide text-muted">{t("name")}</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full text-sm border border-border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-kb"
          />
        </div>

        <fieldset className="space-y-1">
          <legend className="text-xs uppercase tracking-wide text-muted">
            {t("aiaAccess", { label: ws.singular })}
          </legend>
          <div className="flex flex-col gap-1">
            {AIA_OPTIONS.map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 text-sm py-1">
                <input
                  type="radio"
                  name="aia_access"
                  value={opt.value}
                  checked={aiaAccess === opt.value}
                  onChange={() => setAiaAccess(opt.value)}
                  className="w-4 h-4 accent-kb"
                />
                <span>{t(opt.labelKey, { label: ws.singular, plural: ws.plural })}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="space-y-1">
          <legend className="text-xs uppercase tracking-wide text-muted">{t("tools")}</legend>
          <div className="flex flex-col gap-1">
            <label className="flex items-center gap-2 text-sm py-1 border-b border-border-soft pb-2">
              <input
                ref={toggleAllRef}
                type="checkbox"
                checked={allSelected}
                onChange={toggleAllTools}
                className="w-4 h-4 accent-kb"
              />
              <span className="font-medium">{t("toolsSelectAll")}</span>
              <span className="text-xs text-muted-soft">({selectedToolsCount}/{allToolsCount})</span>
            </label>
            {availableTools.map((key) => (
              <label key={key} className="flex items-center gap-2 text-sm py-1">
                <input
                  type="checkbox"
                  checked={tools.has(key)}
                  onChange={() => toggleTool(key)}
                  className="w-4 h-4 accent-kb"
                />
                <span>{tTools(key as Parameters<typeof tTools>[0])}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {error && <p className="text-sm text-error">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] disabled:opacity-60"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving || !name.trim()}
            className="px-4 py-2 text-sm bg-kb text-white rounded-md disabled:opacity-60"
          >
            {t("save")}
          </button>
        </div>
      </div>
    </div>
  );
}
